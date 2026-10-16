#import "../template.typ": *
#show: doc.with(
  title: "Guide 5 · Free AI Coding Tools",
  subtitle: "Which free coding agent to use, how to set it up, and the rules for using it on AgriAgent",
  date: "16 October 2026",
)

#show table: set par(justify: false)
#set par(justify: false)
#show raw.where(block: true): set text(8pt)

#note(title: "In one line")[
  Use *Google Antigravity* first, *Codex (GPT-6 Luna)* when Antigravity's weekly limit runs out, and
  *claude.ai* to have code explained. Whatever the tool, follow the rules in Section 4. The rules matter
  more than the model.
]

= Which tool for what

#table(
  columns: (auto, 1fr, 1fr),
  [Tool], [Use it for], [Free limits (checked 16 Oct 2026)],
  [*Google Antigravity* (desktop IDE)], [Main coding agent: your track's tasks, fixing your defects, writing tests.], [Free tier with a *weekly* cap on agent runs. Models include Gemini 3.x; Claude Sonnet/Opus 4.6 are reported to leave the free tier on *2 Nov*.],
  [*Codex* app / CLI with *GPT-6 Luna*], [Second agent when the Antigravity cap is hit; small, clearly described tasks.], [Luna is available to Free and Go ChatGPT users in the Codex desktop app.],
  [*GitHub Copilot Student*], [Autocomplete and quick questions inside VS Code.], [Free with a verified college email. Model is chosen automatically ("Auto"); you cannot pick Claude.],
  [*claude.ai* (free chat)], [Understanding: paste one function, ask it to explain, quiz you, find the bug.], [Limited messages per day. Chat only, no repo access.],
)

#warn(title: "Do not use")[
  Our project's *Groq or Cloudflare keys* inside a coding agent: agents send very long prompts, and
  Groq's free 8,000 tokens per minute would stall them. Those keys are for AgriAgent itself. Also skip
  Qwen Code's free login (reported shut down in April 2026) and OpenRouter `:free` models (about 50
  requests a day).
]

= Setting up

== Google Antigravity

+ Download from `https://antigravity.google` (Windows, macOS, Linux). Sign in with your Google account. No card.
+ *File → Open Folder* → your `agriAgent` folder.
+ Open the agent panel. In the model selector, check which models *your* account has. Google has
  changed the free list several times, so trust the selector, not blog posts.
+ First message of every session: the rules prompt from Section 4.

== Codex with GPT-6 Luna

+ Desktop app: `https://developers.openai.com/codex` → download, sign in with your ChatGPT account.
+ Or the CLI (needs Node.js 18+):

```bash
npm install -g @openai/codex
cd agriAgent
codex --model gpt-6-luna
```

3. Codex reads a file named `AGENTS.md` in the repo automatically, if one exists. Until it does, paste the Section 4 prompt.

== GitHub Copilot Student (optional)

+ Apply at `https://education.github.com/pack` with your college email (or a photo of your ID card).
  Approval can take a few days; new sign-ups are reopening in phases.
+ Then `https://github.com/settings/copilot` → enable, and install the *GitHub Copilot* extension in VS Code.

= How to use an agent on a task (the workflow)

+ *Pick one task from the schedule* (for example `T3.5`) and create a branch:
  `git checkout main && git pull && git checkout -b sahil/T3.5-crop-metric`
+ *Give the agent the task text from the schedule*, word for word, including its "Done when" line.
+ *Ask for a plan first:* "Before writing code, list the files you will change and why." Reject a plan
  that touches another track's folder or adds a library.
+ *Let it write the code. Then read the diff yourself* (`git diff`). If you cannot explain a line, ask
  the agent to explain it, or remove it.
+ *Run the checks yourself*, not the agent's word for it:

```bash
PYTHONPATH=. python -m unittest discover tests
ruff check . && ruff format --check .
```

6. *Open a pull request* that says which task it is and pastes the test output. Chaitanya reviews it.
7. *Explain-back:* before the PR is merged, explain the change to a teammate in 2 minutes. If you
  cannot, you are not ready for the viva question about it.

= The rules (paste this at the start of every agent session)

```text
You are helping on AgriAgent, a final-year college project. Rules:
1. Read README.md and docs/AgriAgent_Project_Map.typ before changing anything.
2. Only edit files of my track: <your folders, e.g. src/evaluation/ and data/>.
   Ask before touching any other folder.
3. Do not add libraries, change model names, or create new documents.
4. Never write "verified", "complete", "real" or "100%" unless you ran a
   command and show its output. Mock output must always be called mock.
5. Keep changes small: one task per session. Show me a plan before coding.
6. Add or update a unit test for every behaviour you change, and run
   PYTHONPATH=. python -m unittest discover tests before you say you are done.
7. Never commit or print secrets. .env stays out of Git.
8. Do not add any AI attribution (Co-Authored-By or "Generated with") to commits.
```

Also: *one agent at a time* in a folder (two agents editing the same files cause the kind of mess we cleaned up on 11 October), and never let an agent push to `main` directly.

= Using AI to learn (for the viva)

These prompts work in any of the tools. Use them on *your own track's* files.

- "Explain `src/evaluation/iou_dice.py` line by line as if I am a second-year student. Then ask me 5 questions about it, one at a time, and tell me if my answer is right."
- "Here is a function from our project. What happens if the input list is empty? If the mask is all zeros? Show me how you would test it."
- "An examiner asks: why did you use Grounding DINO instead of training YOLO? Give me a 3-sentence answer, then attack it like an examiner would."
- "I changed this line from `>` to `>=`. What behaviour changes, and which test would catch it?"

Then close the AI and explain it again from memory. Guide 0's study loop (read, open the code,
explain without looking, find the gap) still applies.

= Links

#table(
  columns: (auto, 1fr),
  [What], [Where],
  [Google Antigravity], [`https://antigravity.google`],
  [OpenAI Codex (app, CLI, docs)], [`https://developers.openai.com/codex`],
  [GitHub Student Developer Pack], [`https://education.github.com/pack`],
  [Copilot settings], [`https://github.com/settings/copilot`],
  [Claude (free chat)], [`https://claude.ai`],
  [Our schedule (tasks, Appendix A keys)], [`docs/AgriAgent_Schedule.pdf`],
  [Our study guides 0–4], [`docs/guides/`],
  [Test runbook (Amit, Sahil)], [`docs/testing/System_Test_Runbook_Cycle0.pdf`],
)

#text(9pt, fill: muted)[Free tiers change often. Limits above were collected from public reports on
16 October 2026; check the model selector and plan page in your own account.]
