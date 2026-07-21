# Task 16: Seed New Opted-In Members & Sponsor Businesses

## Objective

Expand the directory demo by opting in additional members and creating
business/sponsor profiles for organizations the board has identified.

---

## 1. New opted-in members

These members were identified by the board as people who would likely
opt in. Add them to `OPTIN_AND_BADGES` in `scripts/seed_enrichment.py`.

| Name                       | ID  | Email                         | Status  | Notes                          |
|----------------------------|-----|-------------------------------|---------|--------------------------------|
| David Arkin and Anni Tilt  | 442 | david@arkintilt.com           | active  | Architecture firm              |
| Ian Smith                  | 47  | nature_controls@yahoo.com     | expired | —                              |
| Lotus Grenier              | 592 | lotus@thrulinepartners.com    | active  | Thruline Partners (business)   |

**Lotus Grenier** should also be linked to a business profile for
"Thruline Partners" (see Task 17 for the business-member linkage
pattern; for now, create a demo business entry for Thruline Partners).

---

## 2. Sponsor / business profiles to create

The board provided a list of sponsors and business contacts. Some
already exist as individual members in the WP data; others will need
synthetic business entries (high IDs like 9004+).

### Already in the database (update `entry_type` → `business`, opt in)

| Business                | Contact             | Member ID | Email                              |
|-------------------------|---------------------|-----------|------------------------------------|
| Love Schack Architecture| Paula               | 428       | Stasha@paxsonfay.com               |
| Durra Panel USA         | Maria Giatrelis     | 563       | maria@durrapanelusa.com            |
| Durra Panel USA         | Todd Giatrelis      | 564       | todd@durrapanelusa.com             |
| Verdant Structural      | Anthony Dente       | 162       | anthony@verdantstructural.com      |
| Hempitecture            | Thomas Gibbons      | 599       | Tommy@hempitecture.com             |
| Silacote                | David Rosprim       | 475       | silacote@silacote.com              |
| Tyler Survant / Building Bureau | Tyler Survant | 462 | tyler@buildingbureau.org           |
| Enrico Bonilauri / Emu Passive | Enrico Bonilauri | 370 | enrico@emupassive.com          |
| James Henderson / Gold Hill Clay Plaster | James Henderson | 359 | james@nwnaturalhomes.com |

### Not in database — create as demo businesses (ID ≥ 9004)

| Business                | Contact             | Email                          | Phone            |
|-------------------------|---------------------|--------------------------------|------------------|
| 475 Supply              | Johnny Rezvani      | jr@475.supply                  | 800-995-6329     |
| Faswall                 | Joseph Becker       | josephb@faswall.com            | (541) 908-6903   |
| Clearwater Credit Union | Erin White          | Erin.White@clearwatercreditunion.org | 406-493-3357 |
| Ind Hemp                | Mike Cook           | mike.cook@indhemp.com          | (406) 622-5680   |
| Hempitecture (alt)      | Mattie Mead         | mattie@hempitecture.com        | —                |
| Thruline Partners       | Lotus Grenier       | lotus@thrulinepartners.com     | (406) 414-7744   |

**Note:** Hempitecture already has Thomas Gibbons (ID 599). Mattie Mead
is a second contact — consider linking both to one Hempitecture business
profile (see Task 17).

**Note:** Johnny Rezvani exists as ID 91 (expired) but under personal
email. Create 475 Supply as a separate business entry.

---

## 3. Implementation

### Update `scripts/seed_enrichment.py`

1. Add the three new members to `OPTIN_AND_BADGES`.
2. Add or update `DEMO_BUSINESSES` with the sponsor entries above.
3. For existing members being converted to businesses:
   - Set `entry_type = "business"`
   - Set `organization` to the business name
   - Set `tags_csv` to include `"sponsor"` where applicable
   - Set `opted_in = True`
4. For new synthetic entries (ID ≥ 9004):
   - Create `Member` + `DirectoryProfile` records
   - Set appropriate fields from the table above

### Logos

- Attempt to find logos from the business websites. Store as
  `logo_url` pointing to the business's own hosted image (same pattern
  as The Last Straw, Living Craft).
- If no logo is found, leave `logo_url = None`.

---

## Deliverables

- [ ] Update `OPTIN_AND_BADGES` with David Arkin, Ian Smith, Lotus Grenier
- [ ] Create/update business profiles for all sponsors listed above
- [ ] Find and set logo URLs where available
- [ ] Run `seed_enrichment.py` and verify entries appear in directory
- [ ] Verify "Show all" toggle shows the full count
