# LUMI GPU recipe (dry run passed 5 Nov 2026, 23:40)

- Web UI: https://www.lumi.csc.fi -> Log in (CSC: viskelis + password + authenticator code). No SSH key needed.
- Apps -> Jupyter. Project: project_462001520. Partition: dev-g (short jobs, started in ~30 s) or small-g (longer).
  1 GPU (MI250 GCD), 7 CPU cores (shows as 14 threads), 32 GiB, time hh:mm:ss. Python: lumi-multitorch (default version).
- Then My Interactive Sessions -> click "Connect to Jupyter" yourself (automation lands on a password page).
- Verified: torch 2.11.0 + ROCm 7.2, device "AMD Instinct MI250X", torch.cuda.is_available() == True (AMD uses the cuda API name),
  ~19 TFLOPS fp32 matmul including warm-up.
- Shared quota for all hackathon members (~4,570 GPU h left on 5 Nov): request only what you use; cancel idle sessions.
- Rule: never put LUMI in the live demo path. Train / batch-process offline, save outputs (models, labels, scores) and demo from those.
- Move files: Jupyter upload button or the web UI file browser; keep data in /scratch/project_462001520/<team-folder>, delete after the event.
- Confidential company data (e.g. FORCIT): check the NDA before uploading anything to LUMI.
