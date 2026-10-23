# Input data review — round 2 (2026-10-23, repo @ 614bfaa on branch final-checks-after-code-review)

Basis: the user's local working copy = commit 614bfaa plus untracked files (cf_comparison.csv, validate_cfs.py, the generated CO2_Pipeline_costs_per_arc.csv, and a leftover PowerPlant_Coal.json). Eight sub-agents checked git history and issues, ran the input pipeline end-to-end, and covered costs, capacity factors, demand, CO2 storage, renewable potentials and existing capacities. Issue pages were read one by one with WebFetch, because the GitHub API and list pages are blocked.


## Issues/PRs closed but not (fully) resolved
- **#44:** the existing-offshore 1995 production profiles are untouched. About 8 nodes sit at CF 0.30–0.34 and 6 NaNs remain; PR #61 only regenerated the new-build CFs.
- **#46:** the per-arc pipeline capex is put on a 25-year basis, but the JSON annualises it over 50 years, so it is about 8.5% low. Lifetime was set 50→25→50 (commit 1fa1213).
- **#39:** CO2 storage went from 7.01 to 69.03 €/t, citing the Rekenkamer report. That report gives a Porthos fee cap of 47.10 €/t, and the figure likely includes transport, which the model already costs separately.
- **#38/#41/#42 (DE pumped hydro 620 GWh; NO inflow 164–181 TWh), #48 (demand), #64 (DE–NL 12.2 GW, BE–NL 5.6 GW, SuedLink, label):** closed without code changes.
- **#52 "Check edgars suggestions":** still open.

## Fixed
- Duplicate storage entries (CO2_Storage column added).
- Sea-crossing pipelines now costed as offshore, with a 1.1 detour factor applied once.
- UK_H–UK2 length corrected.
- DAC caps per node: 3.8 Mt/yr onshore, 0.4 Mt/yr offshore.
- Network fixed O&M on an annualised basis.
- Pipeline O&M about 4%.
- DEA 2040 costs; PV now utility-scale.
- DE coal and BE nuclear removed (BE nuclear is a policy caveat: the phase-out law was repealed in 2025).
- NO_D moved; its CF is now 0.47–0.53 and it is linked to the CO2 network.
- connection_matrix_existing KeyError.

## New concerns
- **DAC capex 5,673 €/(t/yr):** this is the Sievert first-of-a-kind cost, about 3.2× the previous value and about 20× DEA 2040.
- **Offshore wind capex 3.84 M€/MW:** DEA far-shore includes the grid connection, so it may double-count the DC links.
- **PPI conversion:** a total-industry PPI is used, and price-year labels are inconsistent (gas VOM tagged 2015).
- **CO2 storage limits:** the total is now 78 Mt/yr, close to DAC nameplate of about 73 Mt/yr, so storage may bind regionally. The values are a mix of sources rather than phase-1 values throughout: NO_B and NO_D went up, and UK_C and DK_C have the same 500 Mt size. Commit 5e6ce47 also touched mes_north_sea nodes_2040.xlsx.
- **Thesis p.31:** DAC demand is stated as "0.07–0.8% of system demand". Against about 1,595 TWh of demand it is about 0.9–6.7%.
- **Smaller code points:**
  - fluid.py hardcodes terrain Offshore, 60 €/MWh and 8000 h;
  - technology.py still warns "OPEX NOT CORRECT IF NOT USED FOR MES NS STUDY";
  - a debug print is left in create_input_data.py;
  - 18 dead new AC arcs with size_max 0;
  - DE_G–DE_H duplicated in the DC line file;

## Demand
Unchanged. Electrolysis is excluded in the TYNDP National Trends scenario, which explains part of the DE gap; this should be stated in the thesis. The UK 21:00 step comes from the source profile and is likely genuine. The calendar mismatch is minor.