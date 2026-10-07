# Demo script: Promotion Performance Attribution

**Length:** about 15 minutes plus Q&A.
**Audience:** mixed business and technical.

How to read this script:
- **SAY** lines are plain language, for everyone.
- **TECH** lines are optional depth for a technical audience. Skip them if the room is non-technical.
- **CLICK** lines tell you what to do on screen.

---

## Before you start (checklist)

1. Start the app: `cd D:\Claude_Training\Capstone\promo_attribution` then `python run.py`.
   Wait for `Application startup complete`.
2. Open **http://127.0.0.1:8000** and check that the Portfolio page loads.
3. Pre-load the test results, so nobody waits 20 seconds live: on **The method** page, click **Run test suite now** once.
4. Have a terminal open in the project folder for the CLI moment in Part 6.
5. Zoom the browser to about 110% so people at the back can read it.

---

## Part 0 · The hook (1 min)

**SAY:**
> "Here's a question every retailer argues about: *did that promotion work?*
>
> Take our Yogurt 15%-off promotion. Ask the sales team, who compare the promo weeks with the weeks just before, and they'll tell you sales went **down 5%**, so it failed.
> Ask the category team, who compare stores that ran it with stores that didn't, and they'll tell you it drove **+115%**, so it was a huge success.
>
> Same promotion, same data, opposite conclusions. It depends on whose spreadsheet you trust.
>
> The real answer is **+15%**. I know that for certain, and by the end of this demo you'll see how I know."

**Why this works:** it states the business problem from the brief ("argued rather than measured") with a concrete number from the data.

---

## Part 1 · What we built, in one minute

**SAY:**
> "Instead of a spreadsheet, the calculation is now a **service**: a piece of software with the rules written down in code. Three things make it trustworthy:
>
> 1. **The method is fixed and written down.** What counts as 'normal sales', which stores we compare against, and how we compute the uplift are all decided once, documented, and version-numbered. Nobody picks them per report.
> 2. **Every number comes with its uncertainty.** Not just '+15%', but '+15%, and we're 95% sure it's between +14% and +17%'.
> 3. **We proved it works, and nobody can quietly break it.** We tested it on data where we hid the right answers, and any change to the method must pass that test before it can go live."

**TECH (one line):**
> "Python service with FastAPI; the method is a versioned package (`attribution/`) with a YAML config; pytest suite; a CI workflow gates merges on a planted-effect recovery test."

---

## Part 2 · Portfolio page: the results (2 min)

**CLICK:** Sidebar → **1 Portfolio**.

**SAY (point at the tiles):**
> "Twelve promotions, all measured the same way. Ten genuinely increased sales. One had **no measurable effect**, and one actually **hurt** sales."

**SAY (point at the chart):**
> "Each blue dot is our best estimate of the uplift. The line through it is the **margin of error**, like the '±3%' on an opinion poll. A short line means we're confident; a longer line means less certain.
>
> The hollow grey circles are what the old pre/post spreadsheet would have said. Look how far off they are. Summer Soda: the spreadsheet says **+49%**, the real effect is about **+23%**. Teams were taking credit for twice the real result."

**SAY (point at the ROI column):**
> "This changes decisions. Both buy-one-get-one promotions, chips and frozen pizza, drove big volume (+30% and +26%) but **lost money**. Their ROI is deeply negative, because giving away half the product costs more than the extra sales earn. A volume-only spreadsheet would have called them the best promotions of the year."

**TECH:**
> "Uplift = actual ÷ counterfactual − 1 over the promo weeks, treated stores, promoted SKUs. 'Significant' means the 95% bootstrap interval excludes zero. ROI = (incremental margin − funding cost) ÷ funding cost."

---

## Part 3 · Promotion deep-dive: the counterfactual (3 min) ★ main moment

**CLICK:** Click the **P09 Holiday Chocolate Gifting** row, or use the dropdown.

**SAY (point at the big chart):**
> "This is the heart of it. The **blue line** is what the stores actually sold. The **orange dashed line** is the **counterfactual**: what they *would* have sold if we hadn't run the promotion.
>
> You can't observe that directly. So we build it from **'twin stores'**: stores of the same type, in the same region, that didn't run the promotion and whose sales moved in step with ours in the months before.
>
> See the big spike at Christmas? A naive analysis credits that spike to the promotion. But the twin stores spiked at Christmas too, so the orange line rises with it. Only the **gap** between blue and orange counts as the promotion's effect: **+18.6%**."

**SAY (point at the shaded bands):**
> "The light blue zone is the **baseline**, the 'normal' weeks we measure against. The grey weeks were deliberately **thrown out**: one was a holiday and one was the week right before launch. A fixed rule decides this, not an analyst, so it can't be massaged."

**CLICK:** Scroll to **"One promotion, three answers"**.

**SAY:**
> "Three ways to measure the same promotion: comparing promoted vs. non-promoted stores says **+100%**, pre/post says **+25%**, and the method says **+18.6%**. The true planted effect is **+18%**."

**CLICK:** Scroll to **"How sure are we?"**.

**SAY:**
> "We re-ran the calculation 1,000 times, each time shuffling which stores are included. The estimates cluster tightly between about +17% and +20%, and none are near zero. So we're confident this effect is real."

**CLICK:** Scroll to the **treated stores and their matched controls** table.

**SAY:**
> "Full transparency: every promoted store, the three twin stores it was compared with, and how closely they matched. Anyone can audit this."

**TECH:**
> "Per treated store: exact match on format and region, then rank candidates by normalised RMSE of weekly sales over a 26-week pre-window, and keep the top 3. The counterfactual is the mean of the controls scaled by the baseline ratio. This is difference-in-differences in ratio form, so common shocks like seasonality, holidays and trend cancel. The CI is a two-stage bootstrap: Poisson re-weighting of controls plus resampling of treated stores. It's seeded, so it's reproducible."

**OPTIONAL:** Switch the dropdown to **P06 Detergent Loyalty Points**.
> "Here the margin of error crosses zero, so the verdict is **'No measurable effect'**. A spreadsheet would have reported −10% and someone would have argued about it. We just say: we can't tell this apart from zero."

---

## Part 3b · Ask: questions in plain English (1.5 min)

**CLICK:** Sidebar → **3 Ask**. Click the chip **"How did P09 perform?"**, then **"What about its ROI?"**.

**SAY:**
> "Not everyone wants to read charts. Here a manager can just ask. Notice two things.
> First, every number has a little **E1** tag. That's the evidence it came from. Click it and you see the exact record from the attribution.
> Second, the green badge says **'15 of 15 numbers verified'**. Before any answer is shown, the system checks that every number in it really exists in the evidence. It can't make numbers up.
> And it understood 'its ROI' meant the chocolate promotion from the previous question."

**CLICK (optional):** Type **"Which mechanics work best on average?"**.
> "Buy-one-get-one drives the most volume, but bundles and display promotions are the profitable ones."

**TECH:**
> "Deterministic intent routing and templated answers over the service's own results. No LLM, so it's reproducible. A number verifier matches every figure in the text to the evidence after %/k/M scaling and rounding. A 17-question evaluation set in pytest gates it like the rest of the method."

---

## Part 4 · The method page: rules written down (1.5 min)

**CLICK:** Sidebar → **4 The method**.

**SAY:**
> "The brief said *'the method is the deliverable as much as the number'*. Here it is. This page is generated from the actual files in the code repository:
> - the **written specification**: what the baseline is, how twin stores are chosen, how uplift is calculated, and the known limitations;
> - the **settings file**, with a version number (we're on **1.2.0**);
> - the **changelog**: every change to the method, why it was made, and its test result.
>
> If finance asks 'how did you get this number?', the answer is a link, not a conversation."

**SAY (point at the tiles):**
> "**89 automated tests**, all passing. The rules that define the baseline are **100% covered by tests**: every rule (skip holidays, skip the pre-launch week, skip weeks with another promotion, refuse if there's too little history) has its own test."

**TECH:**
> "Baseline rules B1–B5 live in `attribution/baseline.py`, with 100% line coverage. CI enforces a 95% floor on that module specifically."

---

## Part 5 · Ground-truth validation: we know the answer (2 min) ★ the proof

**CLICK:** Sidebar → **5 Ground-truth validation**.

**SAY:**
> "How do we know the method is right? With real sales you never know the true effect, so we can't grade it.
>
> So we built a **realistic simulated retailer**: 100 stores, 40 products, two years of weekly sales. We **planted** a known effect in each promotion, like hiding the answer key. Then we ran the method **without letting it see the answers**, and checked its work.
>
> The **black diamonds** are the planted truth. The **blue dots** are what the method found. The grey bar is our promise: within **±2 percentage points**.
>
> Result: **12 out of 12** recovered. The largest miss was under **1 point**. It correctly found the zero-effect promotion and the negative one."

**SAY (point at the 'Spreadsheet error' column):**
> "For comparison, the spreadsheet method missed by up to **27 points** (Summer Soda)."

**SAY (scroll to the calibration panel):**
> "One test could be lucky, so we generated **30 completely different simulated retailers** and repeated the test 360 times. **99% of estimates** landed within ±2 points. That's why we can state the tolerance with confidence."

**TECH:**
> "The simulated data includes deliberate traps. Seasonality differs by store format and trend differs by region, so stores aren't interchangeable. Treated stores are skewed towards large stores, so 'all untreated' is a biased control. There are holidays and repeat promos on the same SKUs. The method code never reads the ground-truth file, and a test checks that."

---

## Part 6 · Reproducibility: same answer every time (1 min)

**CLICK:** Sidebar → **6 Reproducibility** → **Run attribution again** (5 runs).

**SAY:**
> "Remember 'it depends who reports it'? Here we re-run the whole analysis 5 times from scratch. Each run produces a **fingerprint**, a unique code for every number in the results. All 5 are **identical**, down to the last digit.
>
> Same data plus same method version means the same answer, whoever runs it and whenever."

**TECH:**
> "SHA-256 over all reported values. Each promotion gets its own seeded RNG stream, so results don't depend on run order. Tests also confirm the data generator reproduces the CSVs byte for byte."

---

## Part 7 · The method-change gate: nobody can quietly break it (3 min) ★ the finale

**CLICK:** Sidebar → **7 Method-change gate**.

**SAY:**
> "Methods evolve. Someone always has a 'small improvement'. The danger is that a change silently shifts every number and nobody notices. So any change has to pass this **gate** before it goes live. Think of it like a car's MOT."

**CLICK:** Select **"More bootstrap iterations"** → **Run gate**.
> "A harmless technical change. The method still finds all the planted answers → **PASS**. Safe to ship."

**CLICK:** Select **"Match controls on format only"** → **Run gate**.
> "Now a change that *sounds* sensible. A category manager says: 'requiring same-region twin stores is too strict, just match on store type.' Reasonable, right?
>
> **BLOCKED.** Look at the chart: on Summer Soda the error jumps past the 2-point limit. Stores in different regions grow at different rates, so the twins stop being twins. Nobody would have caught this by eye, but the gate did."

**CLICK:** Select **"Use every untreated store as control"** → **Run gate**.
> "Finance suggests using *all* other stores, since a bigger sample must be better. **BLOCKED**: only 2 of 12 recovered, with errors up to 9 points. Bigger isn't better if the comparison is unfair."

**CLICK:** **Build your own change** → set **Tolerance** to `50` and **Control strategy** to `none` → **Run gate**.
> "Could someone cheat by loosening the rules they're judged by? **No.** The gate always uses the official tolerance, and flags the attempt (check G5)."

**TECH:**
> "Five checks: G1 recovery, G2 reproducibility, G3 a version bump is required for any method change, G4 the reference data matches pinned checksums, G5 validation thresholds are owned by main. The same `run_gate()` function backs the UI, the CLI and CI."

**OPTIONAL, for a technical audience:** switch to the terminal.

```powershell
python gate.py --config configs\proposals\v1.3.0_match_on_format_only.yaml
echo $LASTEXITCODE        # 1 = blocked
```

> "In GitHub, `.github/workflows/method-gate.yml` runs this on every pull request. A non-zero exit fails the build, so the merge button is blocked."

---

## Part 8 · Data page (30 sec, optional)

**CLICK:** Sidebar → **8 Data**.

**SAY:**
> "All the inputs: stores, products, calendar, promotions, 416,000 rows of weekly sales. Note the answer-key file marked **'hidden from method'**. Each file's fingerprint is locked, so if anyone edits the data, the gate fails."

---

## Part 9 · Close (1 min)

**SAY:**
> "To sum up. The brief asked for four things, and here's the evidence for each:
>
> | Success metric | What you saw |
> |---|---|
> | Recovers the planted effect within a stated tolerance | 12/12 within ±2 points; 99% across 30 simulated retailers |
> | Baseline definition is tested | 100% test coverage on the baseline rules |
> | Reproducible across runs | Identical fingerprints, every run |
> | Gate on a method change | Good change passes; plausible-but-wrong changes are blocked |
>
> Promotion reviews stop being an argument about whose spreadsheet is right. There's **one method, written down, tested, versioned**, and every number comes with its counterfactual and its margin of error."

---

## Q&A cheat sheet

**"This is simulated data. Does it work on real data?"**
> "Simulated data is the only way to *prove* accuracy, because only there do we know the true answer. The method itself reads ordinary sales files. Next step: run it on real data alongside the existing reports, and use the simulated test as the permanent safety net."

**"What if there aren't enough similar stores to compare with?"**
> "The method relaxes its matching one step at a time and **flags it** in the store table. Accuracy drops in that case, and it's documented as a known limitation. The practical fix is to hold back a few stores from each promotion as a control group."

**"Why ±2 points and not tighter?"**
> "We measured it rather than guessed: the 99th-percentile error across 360 tests is 1.7 points. Promising tighter would make the gate fail randomly."

**"How often would it wrongly call a zero-effect promo a success?"** *(be honest)*
> "In the 30-world test, the zero-effect promotion was flagged as significant in 4 of 30 worlds, about 13%, against a 5% target. That's a known area to improve in the next method version. The gate is exactly how we'd prove any improvement."

**"What doesn't it measure?"**
> "Halo effects on other products, cannibalisation, and the post-promotion dip are out of scope for v1. They're listed in the method's limitations section."

**"Is the Ask feature an AI chatbot? Can it hallucinate?"**
> "No. It's deterministic: it routes the question and fills answers from the service's own results. Every number is checked against the cited evidence before it's shown, and the same question always gets the same answer. An AI model could be added later just to rephrase answers, with the same number check as a guardrail."

**"How long does it take to run?"**
> "All 12 promotions with 1,000 bootstrap draws each take under a second. The full test suite takes about 20 seconds."

---

## Plain-language glossary

| Term | Say it like this |
|---|---|
| Counterfactual | "What would have happened without the promotion" |
| Baseline | "Normal trading weeks we compare against" |
| Control / twin stores | "Similar stores that didn't run the promo" |
| Uplift | "Extra sales caused by the promotion, as a %" |
| Confidence interval | "Margin of error: the range we're 95% sure the true value is in" |
| Significant | "The margin of error doesn't include zero, so the effect is real" |
| Planted effect / ground truth | "The hidden answer key we tested against" |
| Bootstrap | "Re-running the calculation many times with shuffled stores to see how much the answer wobbles" |
| Fingerprint | "A unique code summarising every number; identical code means identical results" |
| Gate / CI | "An automatic check that blocks a change from going live unless it passes" |
| Difference-in-differences | "Compare how much promoted stores changed vs how much their twins changed" |

---

## If something breaks live

| Problem | Fix |
|---|---|
| Browser says "refused to connect" | The app isn't running: `python run.py` |
| "Address already in use" (error 10048) | Another copy is running. Just open the URL, or free the port: `Get-NetTCPConnection -LocalPort 8000 -State Listen \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` |
| Charts don't render | Hard refresh with `Ctrl + F5` |
| UI completely down | Show the gate from the terminal: `python gate.py --all-proposals` |
