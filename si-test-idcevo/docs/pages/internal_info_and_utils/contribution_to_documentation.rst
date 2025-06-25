Contribution to documentation
======================================================

You can verify your changes locally and using the CI. To check them locally, execute the following in a Python 3 virtual environment:

.. code-block:: bash

    $ pip install -r requirements-docs.txt
    $ make test

Alternatively, you can have a look at the CI results if you execute build-docs or build-push-docs job in a pipeline that you want: Go to the logs tab of the Zuul build result page and open the file: **html/index.html**, by clicking on it.

Publish documentation into master
------------------------------------

After making you contribution we have a job responsible to build and push it to the github pages.

.. code-block:: yaml

    - job:
        name: build-push-docs

This job will automatically run in the gate pipeline, but if you want to run it manually you can do it, just add it to the test pipeline.
