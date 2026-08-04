# Inventory Intelligence linking

Drug Demand now displays: NUPCO Code, Mosool, and LC.

- NUPCO Code is the matching key.
- Mosool and LC remain blank until Inventory Intelligence data is supplied.
- To complete the live link, provide the current Inventory Intelligence project or its dashboard-data.js/data export.
- The inventory updater should map each NUPCO code to the latest Mosool and LC quantities before writing daily demand JSON files.
