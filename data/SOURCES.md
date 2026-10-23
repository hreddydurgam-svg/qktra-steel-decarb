# Data sources

All documents were opened on 2026-10-14, except sources 27-29 (opened 2026-10-15; the
`retrieved_on` of the rows citing them is 2026-10-15) and sources 30-34 (opened 2026-10-16;
`retrieved_on` 2026-10-16, as for source 24) source 26 (OSRM routes re-queried 2026-10-17; `retrieved_on`
2026-10-17 for `nodes.csv` and `mat.*.dist`) and source 35 (opened 2026-10-17; `retrieved_on` 2026-10-17). Reference month for prices: July 2026 (each row's own date is in the
`price_date` column of `inputs.csv`). Exchange rate: July 2026 RBI average, 95.8210 INR/USD. No USD figure is
converted into a model value; USD figures appear only as cross-checks in notes.

## Sources

1. Reserve Bank of India, Reference Rate Archive (FBIL reference rates), USD, 01-31 Jul 2026, 23 daily values. https://www.rbi.org.in/Scripts/ReferenceRateArchive.aspx. Accessed 2026-10-14. Ids: `fx.inr_per_usd`; file `series/fx.inr_per_usd.csv`.
2. Central Electricity Authority (2026), CO2 Baseline Database for the Indian Power Sector, User Guide Version 22.0, August 2026, Table S (FY 2025-26). https://cea.nic.in/api/cdm-report-version/view-pdf/en/82. Accessed 2026-10-14. Ids: `grid.ef`.
3. Tamil Nadu Electricity Regulatory Commission (2025), Suo-motu Tariff Order No. 6 of 2025, 30-06-2025, Determination of Tariff for Distribution for FY 2025-26 (eff. 01-07-2025). https://www.tnpdcl.org/static/tnpdcl/assets/files/tariff/2025/TO062025/TO62025.pdf. Accessed 2026-10-14. Ids: `grid.price`, `sol.var`, `ppa.price`.
4. Tamil Nadu Electricity Regulatory Commission (2019), Order No. 5 of 2019, 29-03-2019, Order on generic tariff for Solar power and related issues (mirror hosted by CBIP). https://www.cbip.org/Regulations2018/Data/Tamil%20Nadu/TN_Tariff_Orders/1_TN_Solar.pdf. Accessed 2026-10-14. Ids: `sol.*.kwh`, `sol.*.fix`, `ppa.*.kwh`, `ppa.price`.
5. TNERC / TANTRANSCO notice of transmission charges to be collected from 01-07-2025 (Ref. T.O. No. 8 of 2022, Tables 6-8 and 6-9), archived by Prayas (Energy Group). https://archive.prayaspune.org/collection/5/document/1419. Accessed 2026-10-14. Ids: `sol.*.fix`, `ppa.*.fix`.
6. Central Electricity Regulatory Commission (2026), Order in Petition No. 12/SM/2026, 23-08-2026, levellised generic tariff for FY 2026-27, Annexure I, para 11, PDF p.16 (discount factor 9.08%). https://cercind.gov.in/2026/orders/12-SM-2026.pdf. Accessed 2026-10-14. Ids: all `*.fix` rows (discount rate).
7. Ministry of Corporate Affairs, Companies Act 2013, Schedule II Part C, useful lives (official India Code copy), PDF p.278 (15 years) and p.279 (20 years). https://www.indiacode.nic.in/bitstream/123456789/2114/5/A2013-18.pdf. Accessed 2026-10-14. Ids: `opt.*.fix` (asset lives 15 and 20 years).
8. UNDP (2023), Low-carbon Technology Packages for Mini Steel Plants: A Compendium, New Delhi. https://www.undp.org/sites/g/files/zskgke326/files/2023-07/undp_steel_tech_compendium_-_web_version.pdf. Accessed 2026-10-14. Ids: `plant.kwh_aux`, `plant.reheat`, `mat.scrap_*.yield`, `mat.scrap_*.kwh`, `opt.whr.*`, `opt.hot.*`, `opt.pre.*`, `opt.gas.fix`, `opt.shred.*`.
9. UNDP / Ministry of Steel / PwC (2015), Compendium of Energy Efficient Technology Measures for Electric Induction Furnace (EIF) Sector, Table 4. https://www.undp.org/sites/g/files/zskgke326/files/migration/in/EIF-tech-Compendium.pdf. Accessed 2026-10-14. Ids: `mat.dri_bellary.yield`, `mat.dri_bellary.kwh`.
10. IPCC (2006), 2006 IPCC Guidelines for National Greenhouse Gas Inventories, Vol. 2 Energy, Ch. 1, Tables 1.2 and 1.4. https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf. Accessed 2026-10-14. Ids: `fo.ef`, `ng.ef`, NCVs used in `fo.price`, `ng.price`.
11. Ministry of Commerce and Industry (DGCI&S), TradeStat Monthly Import Data, commodity-wise all countries, HS 72044900 (ferrous waste and scrap, other) and HS 27111100 (LNG), quantity and Rs crore, Aug 2023 - Jul 2026. https://tradestat.commerce.gov.in/meidb/commodity_wise_all_countries_import. Accessed 2026-10-14. Ids: `mat.scrap_imp.price`, `ng.price`, `mat.scrap_imp.cap`; files `series/mat.scrap_imp.price.csv`, `series/ng.price.csv`.
12. Ministry of Commerce and Industry (DGCI&S), TradeStat Monthly Export Data, HS 27101959 (furnace oil, grade HV), Aug 2023 - Jul 2026. https://tradestat.commerce.gov.in/meidb/commodity_wise_all_countries_export. Accessed 2026-10-14. Ids: `fo.price`; file `series/fo.price.csv`.
13. Shanghai Metals Market (2026), "[SMM Steel] India domestic Steel and Scrap Prices Rise", 24 Aug 2026. https://news.metal.com/newscontent/104076202-smm-steel-india-domestic-steel-and-scrap-prices-rise. Accessed 2026-10-14. Ids: `mat.dri_bellary.price`.
14. Shanghai Metals Market (2026), "[SMM Analysis] Indian sponge iron prices rise to two-year high amid rising coal costs", 22 Sep 2026. https://news.metal.com/newscontent/104127101-smm-analysis-indian-sponge-iron-prices-rise-to-two-year-high-amid-rising-coal-costs. Accessed 2026-10-14. Ids: `mat.dri_bellary.price`, `con.dri_bellary.disc`.
15. Shanghai Metals Market (2026), "[SMM Steel] India Steel Prices Fall Amid Subdued Trading", 12 Oct 2026. https://news.metal.com/newscontent/104152645-smm-steel-india-steel-prices-fall-amid-subdued-trading. Accessed 2026-10-14. Ids: `mat.dri_bellary.price` (range check).
16. Nitturu, K., Sripathy, P., Patidar, R., Elango, S., Yadav, D., Mallya, H. (2024), Decarbonising Coal-based Direct Reduced Iron Production: Surveying the Landscape in Steel Clusters of India, CEEW Issue Brief, July 2024. https://ceew.in/sites/default/files/decarbonising-coal-based-dri-production.pdf. Accessed 2026-10-14. Ids: `mat.dri_bellary.ef`, `mat.dri_bellary.cap`, `con.dri_bellary.min`, node `ef_prod` for DRI nodes.
17. Bureau of Indian Standards, IS 1786:2008 High strength deformed steel bars and wires for concrete reinforcement, incl. Amendment No. 1 (public.resource.org copy). https://law.resource.org/pub/in/bis/S03/is.1786.2008.pdf. Accessed 2026-10-14. Ids: `lim.p`.
18. Bureau of Indian Standards, IS 15774:2007 Sponge iron/DRI, HBI and CBI for steel making, Table 1. https://law.resource.org/pub/in/bis/S10/is.15774.2007.pdf. Accessed 2026-10-14. Ids: `mat.dri_bellary.p`, `mat.dri_bellary.cu`. Amendment No.1 (PDF p.6) says "Delete `and induction furnaces'" from the scope clause, so the standard no longer covers induction furnace use; its Grade 2 limits are used here as assumed upper bounds.
19. Bureau of Indian Standards, IS 2062:2011 Hot rolled medium and high tensile structural steel, Table 1. https://law.resource.org/pub/in/bis/S10/is.2062.2011.pdf. Accessed 2026-10-14. Ids: `mat.scrap_*.p`.
20. MEDALS project (EU Horizon Europe GA 101138516), Deliverable D2.1 TrampData, KTH Royal Institute of Technology, 27 Dec 2024, Table 3. https://www.medals.proj.kth.se/polopoly_fs/1.1468877.1776073100!/D2.1%20-%20Tramp%20Data.pdf. Accessed 2026-10-14. Ids: `mat.scrap_*.cu`.
21. Daehn, K.E., Cabrera Serrenho, A., Allwood, J.M. (2017), How Will Copper Contamination Constrain Future Global Steel Recycling?, Environmental Science & Technology 51(11), 6599-6606, doi:10.1021/acs.est.7b00997. https://doi.org/10.1021/acs.est.7b00997 (not readable logged out) and open Cambridge repository copy (handle 1810/266889) https://www.repository.cam.ac.uk/bitstreams/86716592-564e-414c-9337-fd92db5f55f1/download. Accessed 2026-10-14; quote re-checked on the Cambridge copy 2026-10-17 (journal p.6599). Ids: `lim.cu`.
22. Maharashtra Pollution Control Board (2022), Executive summary for public hearing, expansion of M.S. billets (induction furnace) and TMT bars (rolling mill), raw material table. https://www.mpcb.gov.in/sites/default/files/public_hearing/exe_summary/2022-04/ex_summary_06042022.pdf. Accessed 2026-10-14. Ids: `plant.roll_yield`.
23. Ministry of Steel (2024), Green Steel Taxonomy, Gazette notification 23-12-2024, clause 4 (emission boundary). https://steel.gov.in/sites/default/files/2026-09/Notification%20green%20steel%20taxonomy%20for%20india%2023.12.2024-reg..pdf. Accessed 2026-10-14. Ids: `mat.scrap_*.ef` (boundary text only: cl.4, PDF p.4, includes "embodied emissions in purchased raw materials and intermediary products" and excludes "transportation emissions"; it does not mention scrap, and the model does count freight).
24. Smart Freight Centre / GLEC (2025), GLEC Framework v3.2, Table 13 Indian road emission intensity values, HCV 20-30 t GVW diesel average, WTW 0.0823 kgCO2e/t-km, Table 13 p.106; original PDF https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311209/61c644c3cbc7aabd60d91cff8d37cff2.pdf and landing page https://smartfreightcentre.org/news/13311209 (also republished by Climatiq). Accessed 2026-10-16. Ids: `nodes.csv` `ef_transport`.
25. OpenStreetMap contributors, Nominatim geocoder (node/way/relation ids per row in `nodes.csv`). https://www.openstreetmap.org/. Accessed 2026-10-14 (commit 08b4600, `nodes.csv` `retrieved_on` 2026-10-14); the `port_vizag` object was looked up again on 2026-10-17. Ids: `nodes.csv` `lat`, `lon`. This source covers every per-node object URL (`https://www.openstreetmap.org/{node|way|relation}/{id}`) in `nodes.csv` `url_or_ref`.
26. OSRM (Open Source Routing Machine) public demo server on OpenStreetMap data, driving route distance to SIPCOT Industrial Complex Ranipet (OSM way 297545907; query `route/v1/driving/{lon},{lat};79.305493,12.961644?overview=false`). https://router.project-osrm.org/. Accessed 2026-10-17 (all routes re-queried 2026-10-17; first queried 2026-10-14 (commit 08b4600, `nodes.csv` `retrieved_on` 2026-10-14); the 2026-10-16 dates set in commit 975128b came from the GLEC URL change, not a re-query). Ids: `nodes.csv` `dist_km`, `mat.*.dist`.

27. NCAER (2025), Assessment of Logistics Cost in India, prepared for DPIIT Logistics Division, September 2025, Sec. 4.6, Table 4.4. https://ncaer.org/wp-content/uploads/2025/09/NCAER_Logistic_Study_Report_Sept2025.pdf. Accessed 2026-10-15. Ids: `freight.tariff`. Verified 2026-10-15 against the downloaded PDF (SHA-256 830f24c6108f19b15261ec4b4ded46fca62c7c42393fd61036b79d51ab082f1f): Table 4.4 on PDF p.90 (printed p.63) gives South->South 4.38, matrix min 2.32 (East->South), max 5.01 (North-east->North-east); national average 3.78 INR/t-km quoted on PDF p.83.
28. Bureau of Energy Efficiency, Guide Book 2 (Energy Efficiency in Thermal Utilities), Ch. 1 Fuels and Combustion, Table 1.2 (furnace oil density 0.89-0.95 g/cc). https://beeindia.gov.in/sites/default/files/2Ch1.pdf. Accessed 2026-10-15. Ids: `opt.pre.fuel`.
29. Tata nexarc blog, "Iron scrap rate today" (updated 9 Oct 2026), citing BigMint 10 Sep 2026 assessment of HMS (80:20) Chennai at Rs 34,300/t. https://blog.tatanexarc.com/da/iron-scrap-rate-today/. Accessed 2026-10-15. Archived copy (verified 2026-10-17): https://web.archive.org/web/20261017013645/https://blog.tatanexarc.com/da/iron-scrap-rate-today/. Ids: `mat.scrap_dom.price`.
30. BigMint (2026), "India: Scrap prices in Chennai increase by INR 600/t w-o-w amid healthy demand - 26 Feb", 26 Feb 2026; HMS (80:20) INR 32,500/t; imported HMS (80:20) $342-345/t CFR Chennai. https://www.bigmint.co/insights/detail/india-scrap-prices-in-chennai-increase-by-inr-600-t-w-o-w-amid-healthy-demand-26-feb-726825 Accessed 2026-10-16. Ids: `mat.scrap_dom.price`, `con.scrap_imp.disc`.
31. BigMint (2026), "India: Ferrous scrap prices rise by INR 300/t w-o-w in Chennai as steel prices improve - 5 Mar", 5 Mar 2026; HMS (80:20) INR 32,800/t; imported HMS (80:20) $355-357/t CFR Chennai. https://www.bigmint.co/insights/detail/india-ferrous-scrap-prices-rise-by-inr-300-t-w-o-w-in-chennai-as-steel-prices-improve-5-mar-728538 Accessed 2026-10-16. Ids: `mat.scrap_dom.price`, `con.scrap_imp.disc`.
32. Shanghai Metals Market (2026), "[SMM Steel] India Domestic Steel Market Sees Price Gains", 27 Aug 2026; scrap INR 32,300/t delivered Chennai. https://news.metal.com/newscontent/104083465-smm-steel-india-domestic-steel-market-sees-price-gains Accessed 2026-10-16. Ids: `mat.scrap_dom.price`.
33. BigMint (2026), "India: Chennai ferrous scrap prices remain firm w-o-w despite billet correction - 8 Oct", 8 Oct 2026; HMS (80:20) INR 35,600/t. https://www.bigmint.co/insights/detail/india-chennai-ferrous-scrap-prices-remain-firm-w-o-w-despite-billet-correction-8-oct-797021 Accessed 2026-10-16. Ids: `mat.scrap_dom.price`.
34. Hidayat, M. (2026), "Asian Ferrous Scrap Prices Ease Further in July 2026", Discovery Alert, 16 Jul 2026; shredded $360-365/t CFR Nhava Sheva, table credits Argus Media. https://discoveryalert.com/asian-ferrous-scrap-prices-july-2026-monsoon-demand-eaf/ Accessed 2026-10-16. Ids: `con.scrap_imp.disc`.
35. Heaven Green Energy, glossary entry "PPA" (vendor page; datePublished 2026-06-04, "Updated 8 July 2026"); minimum offtake "typically 80% to 90%" of expected generation. https://www.heavengreenenergy.com/glossary/ppa. Accessed 2026-10-17. Ids: `ppa.minfrac` (weak source: vendor glossary, not a regulator).

GLEC v3.2 (source 24) and OSRM/OSM (sources 25-26) also support `freight.ef` and `mat.*.dist` (cross-reference
note, not a separate document).

BigMint access (sources 30, 31, 33; checked 2026-10-17): BigMint gives each reader a few free articles and then
asks for a free login. Logged out, the 26 Feb and 5 Mar pages were readable under a counter ("You have 1
complimentary insights remaining!"); the 8 Oct page showed only its headline ("This information is limited to a
select few subscription packages."), so its 35,600 figure can no longer be read logged out. Archiving failed: the
Wayback Machine has no snapshot of any of the three pages, and archive.ph asked for a CAPTCHA (not solved). The
BigMint 10 Sep 2026 assessment is also reported by Tata nexarc (source 29), whose archived copy is listed there.

## Method notes

- Fixed annual costs: annuity = capex x CRF(r, n), CRF = r(1+r)^n / ((1+r)^n - 1), r = 9.08% (source 6).
  CRF(15) = 0.12465, CRF(20) = 0.11017, CRF(25) = 0.10247. Lives: solar 25 years (source 4);
  recuperator, direct rolling, gas conversion 20 years ("Rolling mill in steel plant", source 7);
  shredder and scrap preheater 15 years (general plant and machinery, source 7).
- Capex values are nominal INR as published (UNDP 2023, TNERC 2019); they were not escalated to 2026.
- Fitted series: mean and sample standard deviation of 36 monthly points (Aug 2023 - Jul 2026).
  Revised (R) TradeStat values are preferred over provisional (F) where both exist. Fit statistics
  (`steel.series.write_fits`) are in `series/*.fit.json`.
- Trend test: `mat.scrap_imp.price` has a significant linear trend (trend_p = 0.022) and `ng.price` too
  (trend_p = 0.002). A stationary normal fit is not valid for them, so both use a triangular range over the last
  12 months (Aug 2025 - Jul 2026) with the July 2026 value as mode, flagged assumption. `fo.price`: no
  significant trend (levels trend_p = 0.10; logs trend_p = 0.24), but the normal fit is rejected (KS p = 0.023)
  and so is the lognormal (`fo.price.fit.json`: KS p = 0.11, bootstrap KS p = 0.0015, which accounts for the
  estimated parameters). It therefore uses the same last-12-month triangular range (772.23 / 1,227.7 / 1,784.59),
  flagged assumption.
- Freight: `mat.*.dist` from `nodes.csv` OSRM distances (OSRM queries re-run 2026-10-17): scrap_dom = median of
  Chennai scrap nodes (city_chennai, ind_ambattur, ind_gummidipoondi) = 118.2 km; scrap_imp = port_chennai 125.7 km; dri_bellary = dri_ballari 408.3 km.
  `port_vizag` uses OSM relation/14724956 "Visakha Container Terminal", a container terminal within the port:
  Nominatim has no object tagged "Visakhapatnam Port" (22 queries, 2026-10-17). The earlier object, way/1088347266,
  was a solar plant.
- Solar O&M and insurance: levelised from the year-wise rows of TNERC Order 5 of 2019, Annexure I (source 4, PDF
  p.43): levelised = CRF(9.08 %, 25) x sum_t cost_t / 1.0908^t = 776,056.23 (O&M) and 85,968.48 (insurance)
  Rs/MW/yr. The order itself levelises at 9.53 % (para 7.13.1); the model uses 9.08 % (source 6) for every annuity.
- Capex scaling: linear in the main run; the six-tenths rule is a sensitivity case (`run_all.py` `SENS_VALUES`).
- Preheater fuel: 47.90 l FO/heat x 0.92 kg/l (BEE midpoint) x 40.4 GJ/t (IPCC) / (612.5 - 16.6) kWh = 0.002988 GJ/kWh.

## Price correlation (`correlation.csv`)

Spearman rank correlation on overlapping monthly observations, written by
`steel.scenarios.write_correlation("data/series", inp.stochastic_ids(), "data/correlation.csv")`. The file's
`# ids:` header gives the row order; `steel.scenarios.load_correlation` aligns it to the model's stochastic ids.
`sample()` converts each rho to the Gaussian-copula parameter 2 sin(pi rho / 6) and clips negative eigenvalues
(none here: smallest eigenvalue of the converted matrix 0.30).

| pair | overlapping months | Spearman rho |
|---|---|---|
| `fo.price` ~ `mat.scrap_imp.price` | 36 (Aug 2023 - Jul 2026) | 0.6710 |
| `fo.price` ~ `ng.price` | 36 | 0.3967 |
| `mat.scrap_imp.price` ~ `ng.price` | 36 | 0.3135 |
| `fx.inr_per_usd` ~ each of the three | 1 (daily series covers July 2026 only) | not estimated (< 24 months) |

`fx.inr_per_usd` is a fixed input, so it is not in the matrix; with one overlapping month it could not be
estimated anyway. `mat.scrap_dom.price`, `mat.dri_bellary.price` and `freight.tariff` have no public monthly
series (see Assumptions), so their correlations are set to 0 (independent); this is an assumption, not an
estimate. Pairs with fewer than 24 overlapping months are set to 0 by rule.

## Assumptions

Class (review of 2026-10-17): SOURCED = the value is stated by a public source; METHOD-SOURCED = a public source
gives the method or range, the value is applied by the author; DESIGN CHOICE ONLY = no public source states the
value; "-" = not classified in that review. Ids in `run_all.py` `SENS_IDS` are tested at 0.8x and 1.2x (plus any
`SENS_VALUES`). The 0.8x and 1.2x factor runs are generic +/-20 % cases, not sourced values; for example the
1.2x run on `mat.dri_bellary.ef` (2.50 tCO2/t) is above the 2.08 stated upper bound.

| id | value | class | reasoning |
|---|---|---|---|
| `plant.demand` | 120,000 t/yr | METHOD-SOURCED | Study premise (hypothetical plant). The size lies in the range a consultancy gives for this plant type: "Investment ranges from about INR 150 crore for an induction furnace and TMT rolling mill of 1 to 2 lakh tonnes a year" (IMARC, "Steel Plant Setup Cost in India", https://www.imarcgroup.com/insight/steel-manufacturing-plant-setup-cost-india, page date not shown). Existing mill of 72,000 t/yr TMT in source 22. Not in sensitivity (study premise). |
| `mat.scrap_dom.cap` | 60,000 t/yr | DESIGN CHOICE ONLY | no public source; tested in sensitivity. No public volume data for Chennai domestic scrap; set equal to import cap. |
| `mat.scrap_imp.cap` | 60,000 t/yr | DESIGN CHOICE ONLY | no public source; tested in sensitivity. ~1.3% of India's annualised HS 72044900 imports (source 11) gives the scale only; the share is a choice. |
| `mat.dri_bellary.cap` | 80,000 t/yr | DESIGN CHOICE ONLY | no public source; tested in sensitivity. ~3.4% of the Bellary cluster capacity: "In Bellary, ... which has an installed capacity of 2.36 MTPA" (source 16, PDF p.7); the share is a choice. |
| `scrap.cap0` | 90,000 t/yr | DESIGN CHOICE ONLY | no public source; tested in sensitivity. Scrap-yard handling ceiling without shredder; only a single-project forum example was found, no design norm. |
| `con.scrap_imp.disc` | 0.02 | - | Public bid-offer gaps (buyers bid $5-10/t below offers): 26 Feb 2026 $342-345/t CFR Chennai (source 30); 5 Mar 2026 $355-357/t (source 31); 16 Jul 2026 shredded $360-365/t CFR Nhava Sheva (source 34). Mid gap 7.5 / mid offer 343.5, 356, 362.5 = 2.18 %, 2.11 %, 2.07 %; mean 2.12 %, rounded to a whole percent. |
| `con.scrap_imp.min` | 20,000 t/yr | DESIGN CHOICE ONLY | no public source; tested in sensitivity. One third of supplier cap. |
| `con.scrap_imp.fee` | 0 INR/yr | DESIGN CHOICE ONLY | No public source. No capex attaches to a supply contract and no fee is published. Not in sensitivity (a factor times 0 is 0). |
| `con.dri_bellary.disc` | 0.01 | - | Motivated by transaction vs offer gap of ~INR 300 on 31,300/t (source 14). |
| `con.dri_bellary.min` | 20,000 t/yr | DESIGN CHOICE ONLY | no public source; tested in sensitivity. One quarter of supplier cap. |
| `con.dri_bellary.fee` | 0 INR/yr | DESIGN CHOICE ONLY | No public source; as for the scrap contract. Not in sensitivity (a factor times 0 is 0). |
| `ppa.minfrac` | 0.8 | SOURCED (weak: vendor page, not a regulator) | "The buyer commits to consume at least a defined percentage (typically 80% to 90%) of expected generation." (Heaven Green Energy glossary "PPA", updated 8 July 2026, source 35). No Tamil Nadu regulator take-or-pay benchmark found. Tested in sensitivity (0.64 / 0.96). |
| `mat.scrap_dom.ef`, `mat.scrap_imp.ef` | 0 tCO2/t | METHOD-SOURCED | Cut-off (recycled-content) allocation: no upstream production burden for post-consumer scrap. GHG Protocol Product Life Cycle Accounting and Reporting Standard, PDF p.75: "The recycled content method is also referred to as the cut-off method or the 100-0 method." (https://ghgprotocol.org/sites/default/files/standards/Product-Life-Cycle-Accounting-Reporting-Standard_041613.pdf). Under that method recycling preprocessing stays with the user, so ef = 0 also omits scrap processing (sorting, cutting, baling). Freight emissions are counted separately (`freight.ef` x `mat.*.dist`; node `ef_transport` x `dist_km`). Green Steel Taxonomy cl.4 (source 23) is cited only for its boundary text and does not mention scrap. Alternative method: worldsteel's recycling variant gives scrap a burden ("Global warming potential (100 years) kg CO2-e 1.63" per kg scrap, illustrative; worldsteel LCI study 2020 data release, PDF p.21, https://worldsteel.org/wp-content/uploads/Life-Cycle-Inventory-study-report-2020-data-release.pdf). Not in sensitivity (a factor times 0 is 0). |
| `mat.dri_bellary.ef` | 2.08 tCO2/t DRI | - | Conservative upper bound: CEEW's domestic coal + lump ore case (source 16, Box 1, PDF p.13), while CEEW p.10 says all Bellary-cluster plants use imported coal. CEEW's imported coal + pellets case 1.53 is a sensitivity value. |
| Solar tier sizes 5/10/20 MW, PPA tier sizes 10/20 MW | - | DESIGN CHOICE ONLY | No public source. Design choices; energy and costs per MW are sourced. Not a scalar, so not in sensitivity. |
| Linear capex scaling of UNDP reference units to plant throughput | - | DESIGN CHOICE ONLY | no public source; tested in sensitivity. Used in `opt.whr.fix`, `opt.hot.fix`, `opt.gas.fix`, `opt.pre.fix`. Sensitivity case: six-tenths rule, C_ref x (S/S_ref)^0.6 x CRF = 411,859 / 2,694,336 / 842,094 / 1,334,255 INR/yr (whr / hot / pre / gas). Method source: "Predictions can be made by using the power relationship known as the six-tenths factor rule, if the new piece of equipment is similar to one of another capacity for which cost data are available." (Al-Mustaqbal University College lecture notes, PDF p.4, https://www.uomus.edu.iq/img/lectures21/MUCLecture_2023_10353197.pdf; teaching notes, not peer reviewed); same page: "the 0.6 power should be used only in the absence of information". If the plant installs several reference-size units (likely for the preheater, ratio 3.87), linear scaling is the better model. |
| Scrap P = IS 2062 E250A max; DRI P and Cu = IS 15774 Grade 2 max; scrap Cu = EU E3 spec | - | - | Specification maxima used as conservative upper bounds, not measured averages. IS 15774 Amendment No.1 removed induction furnaces from its scope (source 18). |
| Same yield and kWh for both scrap types | - | - | Source gives one scrap-based unit only. |
| `lim.p` | 0.055 % | SOURCED | IS 1786 Amendment No.1 cl.4.2 (source 17, PDF p.7): Fe 500 P max 0.055. The rebar grade Fe 500 is a choice; Fe 500D (0.040) is infeasible with scrap P maxima. In sensitivity (0.8x, 1.2x and 0.040). |
| `mat.scrap_dom.p`, `mat.scrap_imp.p` | 0.045 % | METHOD-SOURCED | IS 2062 Table 1 (source 19, PDF p.9): "E 250 ... A 0.23 1.50 0.045 0.045 0.40 0.42" (C, Mn, S, P, Si, CE). Specification maximum, not a measured value; no open measured Indian scrap P found. In sensitivity. |
| `opt.shred.extra` | 10,344 t/yr | - | UNDP "Quantity of shredded scrap 3448 kg/heat" (source 8, PDF p.101) is the scrap that is shredded, not extra yard capacity; treating it as added handling capacity is an author assumption. |
| `mat.scrap_dom.price` | tri 32,300 / 32,800 / 35,600 | - | Five public Chennai HMS (80:20) quotes, 26 Feb - 8 Oct 2026 (sources 30-33 and 29), fewer than 24 monthly points; low = min, mode = median, high = max. BigMint access limits: see the note after the source list. |
| `mat.dri_bellary.price` | tri 26,600 / 28,000 / 31,300 | - | SMM points 17 Aug - 12 Oct 2026, fewer than 24 monthly points. |
| `mat.scrap_imp.price` | tri 32,732 / 37,783 / 37,783 | - | Trending series; last-12-month range, July 2026 mode. |
| `ng.price` | tri 890.96 / 1,321.88 / 1,345.54 | - | Trending series; last-12-month range, July 2026 mode. |
| `fo.price` | tri 772.23 / 1,227.7 / 1,784.59 | - | Normal and lognormal fits rejected; last-12-month range, July 2026 mode. |
| `freight.tariff` | tri 2.32 / 4.38 / 5.01 | - | NCAER zone matrix; mode South->South; bounds are matrix min/max, not a time series. |
| FO density 0.92 kg/l | - | - | Midpoint of BEE range 0.89-0.95. |

## Dropped items

- `dri_salem` (template material): no public sponge iron price or emission data for Salem found. Dropped.
- `dri_raipur`: SMM publishes Raipur PDRI EXW prices, but the model price has no freight term and Raipur is
  ~1,245 km by road from Ranipet; including it ex-works would bias the choice. Dropped; Raipur nodes stay in `nodes.csv`.
- `const.demand_charge`: TNERC HT-I demand charge is Rs 608/kVA/month (source 3, p.18), but the plant's
  contract demand (kVA) is a design choice no document gives; the term is a constant that does not change any
  decision in the model. Dropped; listed as an open question.
- `const.*` for ferro-alloys, flux, refractories, water and labour, and `constef.*`: no public price found for
  ferro-alloys (paywalled assessments only); all are decision-neutral constants. Dropped.
- Time-of-day tariff (+25% peak, -5% night) and Tamil Nadu electricity tax on `grid.price`: need a load profile.
  Dropped; base energy charge used.
- Domestic scrap and DRI price series: BigMint/SteelMint historical series are paywalled. Triangular ranges from
  publicly visible articles used instead.

## Reference-date exceptions

Reference month is July 2026. Rows priced or dated outside it:

| id | date of the figure |
|---|---|
| `mat.dri_bellary.price` | mode 24 Aug 2026; range 17 Aug - 12 Oct 2026 (no public July 2026 Bellary quote) |
| `mat.scrap_dom.price` | range 26 Feb - 8 Oct 2026; mode 5 Mar 2026; no public July 2026 Chennai quote |
| `fo.price`, `mat.scrap_imp.price`, `ng.price` | range Aug 2025 - Jul 2026 (mode Jul 2026) |
| `grid.price`, `sol.var`, `ppa.price` | TNERC tariff effective 1 Jul 2025 (still in force; no 2026 revision found) |
| `ppa.price` (generation part 3.04), `sol.*` capex/CUF | TNERC Order 5 of 2019 (29 Mar 2019) |
| `sol.*.fix`, `ppa.*.fix` (LTOA charge) | FY 2025-26 charge from 1 Jul 2025 |
| `freight.tariff` | NCAER survey for FY 2023-24 |
| `opt.*` capex | UNDP compendium 2023 (nominal, not escalated) |
| `grid.ef` | CEA FY 2025-26 |
