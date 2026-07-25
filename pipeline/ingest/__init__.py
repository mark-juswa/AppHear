"""Ingest ASL-recorder (aslrecorder2) clips into the AppHear 3 feature pipeline.

The recorder captures VIDEO; this package re-extracts it with the SAME clip-level stage functions
the ASL Citizen pipeline uses (extract → detect → features) so recorded clips share the exact
landmark dialect, then supplements/replaces a gloss in the conversational feature set for retrain.
Everything writes to NEW dirs — ASL Citizen data and the deployed model are never touched.
See context/recorder-pipeline.md.
"""
