# BI Steward design system (Sat 7 Nov, Gajus)

Sources (cloned to ~/design-refs, read-only): UI UX Pro Max (product rows "B2B Service" + "Analytics Dashboard",
typography "Minimal Swiss"), taste-skill (one system, one accent, plain copy, equal edges, no violet, real product UI),
design-motion-principles (Emil Kowalski lens for SaaS dashboards), Awesome Claude Design (IBM/Vercel enterprise refs).

- Style: Accessible & Ethical + Minimalism & Swiss. Clarity over decoration; status colour only for status.
- Colour: ink #0F172A, one accent #0369A1 (trust blue), slate neutrals (#F8FAFC bg, #E2E8F0 border, #475569 muted);
  good #15803D, warn #D97706, bad #DC2626. Dark navy sidebar. Config: .streamlit/config.toml.
- Type: Inter 400-700 (tabular numbers on KPIs), JetBrains Mono for record-id chips.
- Components (frontend/ui.py): hero, pipeline pills (AI steps tinted), verdict banner, KPI card, gap card (hatched,
  "Not measured yet"), AI trail (numbered steps + id chips + agree/disagree badge), AI takeaway, evidence line.
  No emoji as icons. Every data string is HTML-escaped.
- Motion: hover lift 1px / press scale 0.98, 120-160 ms ease-out; none under prefers-reduced-motion.
