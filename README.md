# Indian administrative location data

The hierarchy is imported from the Local Government Directory (LGD), Ministry
of Panchayati Raj, Government of India:

- Source: https://lgdirectory.gov.in/
- Archive mirror used for the local snapshot:
  https://github.com/planemad/india-local-government-directory
- Snapshot file: `lgd/village-directory.csv`
- Snapshot date: 2026-09-07
- License: Government Open Data License - India (GODL-India)

The CSV contains LGD state, district, sub-district and village codes. The
startup importer loads it into `location_states`, `location_districts`,
`location_subdistricts`, and `location_villages`. Names are display values;
stable LGD codes are stored as unique keys and relationships use database IDs.
