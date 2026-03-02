ORI-C – Fix Cross-Conditions dataset argument

Problem fixed:
- Workflow passed --dataset-path but script requires --dataset, causing argparse failure.

What this pack does:
1) Updates .github/workflows/qcc_stateprob_cross_conditions.yml to call:
   python tools/qcc_stateprob_cross_conditions.py --dataset "<path>" ...

2) Adds a tiny helper module tools/_qcc_cross_argparse_compat.py that your script
   can import if needed to accept both flags. If your current script already
   accepts both, you can ignore this helper.

If your script still fails after applying:
- Open tools/qcc_stateprob_cross_conditions.py and ensure the argparse includes:
  parser.add_argument("--dataset", "--dataset-path", dest="dataset", required=True, ...)
