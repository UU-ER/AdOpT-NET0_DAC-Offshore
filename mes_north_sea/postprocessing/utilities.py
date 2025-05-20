scenarios = {
              'RE_only': ['Baseline', 'Baseline'],
              'Battery_on': ['Storage', 'onshore only'],
              'Battery_off': ['Storage', 'offshore only'],
              'Battery_all': ['Storage', 'all'],
              'Battery_all_HP': ['Storage', 'all, high power-energy-ratio'],
              'ElectricityGrid_all': ['Grid Expansion', 'all'],
              'ElectricityGrid_on': ['Grid Expansion', 'onshore only'],
              'ElectricityGrid_off': ['Grid Expansion', 'offshore only'],
              'ElectricityGrid_noBorder': ['Grid Expansion', 'no Border'],
              'Hydrogen_Baseline': ['Hydrogen', 'all'],
              'Hydrogen_H1': ['Hydrogen', 'no storage'],
              'Hydrogen_H2': ['Hydrogen', 'no hydrogen offshore'],
              'Hydrogen_H3': ['Hydrogen', 'no hydrogen onshore'],
              'Hydrogen_H4': ['Hydrogen', 'local use only'],
              'All': ['All', 'All']
             }


def map_timestamp(timestamp, idx):
    for key, value in scenarios.items():
        if key in timestamp:
            return value[idx]
    return "Baseline"  # or some default value if no match is found
