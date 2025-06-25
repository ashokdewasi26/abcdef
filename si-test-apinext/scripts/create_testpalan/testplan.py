import argparse
from pathlib import Path

from jira import JIRA

URL = "https://jira.cc.bmwgroup.net"
TEMPLATE_TICKETS = {"idc23": "ABPI-552812", "padi": "ABPI-553226"}
OUTPUT_FILE = "testplan_config.yaml"


class JiraTicketManager:
    def __init__(self, token, target):
        self.url = URL
        self.token = token
        self.issue = TEMPLATE_TICKETS[target]
        self.jira = self.connect_to_jira()
        self.ticket = self.get_ticket()

    def connect_to_jira(self):
        try:
            return JIRA(server=self.url, token_auth=self.token)
        except Exception as e:
            print("Unable to create connection! Reason: ", e)
            raise

    def get_ticket(self):
        print("Fetching JIRA Ticket")
        return self.jira.issue(self.issue)

    def create_new_ticket(self, job):
        summary = ""
        job_name = job.lower()
        template_fields = self.ticket.fields
        template_summary = template_fields.summary.lower()
        if "idc23" in job_name and "idc23" in template_summary:
            summary += "[IDC23][ProdSI] " + job
            base_job = "*base_idc23"
        elif "rse22" in job_name or "padi" in job_name and "padi" in template_summary:
            summary += "[PaDi][ProdSI] " + job
            base_job = "*base_padi"
        else:
            print(
                "Expected idc23/rse22/padi keyword in job name:", job_name, "and in template ticket:", template_summary
            )
            return None, None
        description = f"Job link: [https://zuul.cc.bmwgroup.net/zuul/t/apinext/job/{job}]\r\n"
        ticket_data = {
            "project": {"key": template_fields.project.key},
            "issuetype": {"name": template_fields.issuetype.name},
            "summary": summary,
            "description": description,
            "labels": template_fields.labels,
        }
        new_ticket = self.jira.create_issue(ticket_data)
        return new_ticket, base_job


def read_jobs_file(file_path):
    job_set = set()
    with open(file_path) as file:
        for line in file:
            job = line.strip()
            if job and not job.startswith("#") and job not in job_set:
                job_set.add(job)
    return tuple(sorted(job_set))


def write_to_file(out_file, job, basejob, ticket_key):

    data = f"""{job}:
  <<: {basejob}
  test_plan_key: {ticket_key}
"""
    with open(out_file, "a") as outfile:
        outfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="Script to create testplan tickets for IDC23 and Padi")
    parser.add_argument("--token", type=str, required=True, help="JIRA token")
    parser.add_argument("--target", type=str, required=True, choices=TEMPLATE_TICKETS.keys(), help="Target name")
    parser.add_argument(
        "--jobs_file",
        required=True,
        help="File containing job names",
        type=lambda x: Path(x).resolve() if Path(x).exists() else parser.error(f'File "{x}" does not exist'),
    )
    args = parser.parse_args()

    output_file = Path(OUTPUT_FILE)
    if output_file.exists():
        output_file.unlink()

    jtm = JiraTicketManager(args.token, args.target)
    jobs = read_jobs_file(args.jobs_file)

    for job_name in jobs:
        new_ticket, base_job = jtm.create_new_ticket(job_name)
        if new_ticket:
            print(job_name, " --> ", new_ticket.key)
            write_to_file(OUTPUT_FILE, job_name, base_job, new_ticket.key)


if __name__ == "__main__":
    main()
