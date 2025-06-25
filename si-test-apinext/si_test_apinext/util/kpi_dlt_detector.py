# Copyright (C) 2022. BMW Car IT GmbH. All rights reserved.
"""DLT helper functions for KPI tests:
    * We need to take the timestamp of an event start, and another timestamp for this event end.
    * The event could be test rack start up, or route calculation
"""
import logging

from mtee.testing.connectors.connector_dlt import DLTContext
from mtee.testing.support.target_share import TargetShare
from mtee.testing.tools import metadata, retry_on_except, TimeoutError

logger = logging.getLogger(__name__)
target = TargetShare().target


@metadata("syncdlt")
class KPIDltDetector:
    def __init__(self, event_start_dlt_pattern, event_end_dlt_pattern, predict_list=None):
        """
        Pass in two events: one states the beginning of event (like route guidance or start up test rack),
                            the other states the end of event.
        :param event_start_dlt_pattern: dictionary {"apid":xx, "ctid":xx, "payload_decoded": re.compile(r"xxx")}
                                        like ROUTE_CALCULATION_START_DLT_PATTERN
        :param event_end_dlt_pattern: dictionary {"apid":xx, "ctid":xx, "payload_decoded": re.compile(r"xxx")}
                                        like ROUTE_CALCULATION_END_DLT_PATTERN
        :param predict_list: the predicts passed from event_start_dlt_pattern to event_end_dlt_pattern
                             Example: handle is found in event_start_dlt_pattern,
                                      and the event_end_dlt_pattern should be constructed with this handle
                             If predict_list is not None, then "payload_decoded" in event_end_dlt_pattern is
                             a lambda or function.
        """
        self.event_start_dlt_pattern = event_start_dlt_pattern
        self.event_end_dlt_pattern = event_end_dlt_pattern
        # Record the matched event start dlt,
        # so that we could get predicts from the start dlt to fulfill the end dlt pattern
        self.matched_event_start_dlt = None
        self.predict_list = predict_list

        self.context = None

    def __enter__(self):
        """Start watching DLT for matching messages"""
        self.context = DLTContext(
            target.connectors.dlt.broker,
            filters=[
                (self.event_start_dlt_pattern["apid"], self.event_start_dlt_pattern["ctid"]),
                (self.event_end_dlt_pattern["apid"], self.event_end_dlt_pattern["ctid"]),
            ],
        )
        self.context.__enter__()
        return self

    def log_messages(self, messages, log_message):
        logger.debug(log_message)
        for message in messages:
            logger.debug("\t%s", message)

    @retry_on_except(exception_class=TimeoutError, retry_count=10, backoff_time=2)
    def _get_matched_dlt_with_smallest_timestamp(self, dlt_pattern):
        messages = self.context.wait_for(dlt_pattern, drop=True, skip=True)
        self.log_messages(messages, "The matched dlt logs are:")

        # Return the dlt log with the smallest timestamp
        messages.sort(key=lambda x: x.tmsp)
        return messages[0]

    def get_timestamp_for_event_start(self):
        try:
            # Record the matched event start dlt
            self.matched_event_start_dlt = self._get_matched_dlt_with_smallest_timestamp(self.event_start_dlt_pattern)
            return self.matched_event_start_dlt.tmsp
        except TimeoutError:
            messages = self.context.messages
            self.log_messages(messages, "Failed to receive matched dlt logs. The received dlt logs are:")
            raise TimeoutError("Failed to receive matched start logs.")

    def get_timestamp_for_event_end(self):
        try:
            # If predict_list is not None, then we have to construct "payload_decoded" in event_end_dlt_pattern
            if self.predict_list is not None:
                # Get predicts from the matched start dlt
                match = self.event_start_dlt_pattern["payload_decoded"].search(
                    self.matched_event_start_dlt.payload_decoded
                )
                # Fulfill the end dlt with the found predicts
                self.event_end_dlt_pattern["payload_decoded"] = self.event_end_dlt_pattern["payload_decoded"](
                    *(match.group(predict) for predict in self.predict_list)
                )

            return self._get_matched_dlt_with_smallest_timestamp(self.event_end_dlt_pattern).tmsp
        except TimeoutError:
            messages = self.context.messages
            self.log_messages(messages, "Failed to receive matched dlt logs. The received dlt logs are:")
            raise TimeoutError("Failed to receive matched end logs.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop watching DLT"""
        self.context.__exit__(exc_type, exc_val, exc_tb)
