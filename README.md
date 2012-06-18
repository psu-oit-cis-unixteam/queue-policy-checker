Install
=======
Simply run:

    python setup.py install --user
    ~/.local/bin/check-queue --help

Policy
======
At time of writing, the policy reads:
- RT Ticket Handling
  - Non-stalled routine operational tickets
     - Initial response: 1-4 hours
     - Updates within: 8-40 hours
  - Stalled tickets
     - tickets become stalled after customer does not respond for: 40 hours
     - these tickets are closed after: 4 weeks
  - Rejected tickets
     - management has denied the request

Roadmap
=======
- indicating when tickets should be closed
- factoring of presentation away from central classes
