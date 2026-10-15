from pathlib import Path
import pandas as pd
from new_network_connections import distance_km

BASE_DIR = Path(__file__).parent / "clean_data"
TOPO_DIR = BASE_DIR / "networks_topology"


def recalculate_network_arc_lengths(network_path):
    """
    Recalculate network arc lengths using great-circle distance between nodes.
    
    Reads a network topology CSV file, loads node coordinates from nodes.xlsx,
    calculates the distance for each arc, and overwrites the 'length' column.
    
    Args:
        network_path: Path to the network CSV file (e.g., 'CO2_Pipeline.csv')
    """
    # Load node coordinates
    meta = pd.read_excel(BASE_DIR / "nodes" / "nodes.xlsx").dropna(subset=["x", "y"])
    meta["Node"] = meta["Node"].astype(str).str.strip()
    
    # Create coordinates dictionary: node_name -> (lon, lat)
    coords = {row.Node: (row.x, row.y) for row in meta.itertuples()}
    
    # Read the network CSV file
    network_df = pd.read_csv(network_path, sep=";")
    
    # Recalculate distances for each arc
    for idx, row in network_df.iterrows():
        node0 = row['node0']
        node1 = row['node1']

        
        # Calculate distance using great-circle distance
        new_length = distance_km(node0, node1, coords)
        network_df.at[idx, 'length'] = new_length
        print(f"Updated {node0}-{node1}: {row['length']:.2f} km -> {new_length:.2f} km")

    # Write back to CSV
    network_df.to_csv(network_path, sep=";", index=False)


if __name__ == "__main__":
    network_paths = [
        TOPO_DIR / "CO2_Pipeline.csv",
        TOPO_DIR / "electricityAC.csv",
        TOPO_DIR / "electricityDC.csv",
    ]
    for network_path in network_paths:
        print(f"Calculating arc lengths for {network_path}")
        recalculate_network_arc_lengths(network_path)

