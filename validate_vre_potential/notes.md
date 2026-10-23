[This is not AI generated...]
# Problem
- Moving from gis data to python input lead to an error for all offshore nodes containing "," as a decimal seprator.
- Wind offshore potential for these nodes is x1000 too large

# Assessment
- check_2040_results checks if the potentials are actually violated in the results.
- It shows, that they are violated for some scenarios and nodes, mostly for the climate year 1995
- violations are reported in offshore_wind_violations.csv

# Severity
- Offshore wind capacities are partly wrong, but mostly for climate years not reported in the main text of the paper
- cy 2009 (as reported in the main text) has the highest cost potential for synergies/T-All/T-only-offshore. For this
    scenario, no new offshore wind is installed, and thus the violation is not relevant for the main text of the paper.
- For other cy 2009 scenarios, the violation might result in a slight overestimation of the respective scenario.
- The same holds for the other climate years.