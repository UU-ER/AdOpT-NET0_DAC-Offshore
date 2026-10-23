import h5py
import numpy as np
import pandas as pd



def load_nodes_from_h5_results(path):
    """
    Loads all nodes contained in a results file as a list
    """
    with h5py.File(path) as hdf_file:
        nodes = extract_data_from_h5_dataset(hdf_file["topology/nodes"])

    return nodes



def load_carriers_from_h5_results(path):
    """
    Loads all carriers contained in a results file as a list
    """
    with h5py.File(path) as hdf_file:
        carriers = extract_data_from_h5_dataset(hdf_file["topology/carriers"])

    return carriers


def load_periods_from_h5_results(path):
    """
    Loads all carriers contained in a results file as a list
    """
    with h5py.File(path) as hdf_file:
        periods = extract_data_from_h5_dataset(hdf_file["topology/periods"])

    return periods


def extract_datasets_from_h5_group(group, prefix=()):
    """
    Gets all datasets from a group of an h5 file and writes it to a multi-index dataframe

    :param group: group of h5 file
    :return: dataframe containing all datasets in group
    """
    data = {}
    for key, value in group.items():
        if isinstance(value, h5py.Group):
            data.update(extract_datasets_from_h5_group(value, prefix + (key,)))
        elif isinstance(value, h5py.Dataset):
            if value.shape == ():
                data[prefix + (key,)] = [value[()]]
            else:
                data[prefix + (key,)] = value[:]

    return data


def extract_data_from_h5_dataset(dataset):
    """
    Gets dataset from an h5 file

    :param group: group of h5 file
    :return: dataframe containing all datasets in group
    """
    data = [item.decode("utf-8") for item in dataset]

    return data


def export_csv(df, label, filename):
    """
    Makes a button on the side bar that allows for csv export
    :param df: dataframe to export
    :param label: label of button
    :param filename: filename to export
    :return:
    """
    excel_buffer = df.to_csv(index=False, sep=";")
    st.sidebar.download_button(
        label=label,
        data=excel_buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def read_results_from_h5(path_h5):
    """
    Reads the energybalance, technology operation, design and network operation, design into a dict
    """

    def process_k_means(d: dict, column_names, k_means_specs):

        data = {}
        if k_means_specs:

            for key in d:
                period = key[0]
                seq = k_means_specs[(period, "sequence")]
                n_clustered = max(seq)

                if len(d[key]) == n_clustered:
                    data[key] = d[key][seq - 1]
                else:
                    data[key] = d[key]
        else:
            for key in d:
                data[key] = d[key]

        df = pd.DataFrame(data)
        df = df.rename_axis(columns=column_names)
        df = add_time_steps_to_df(df)

        return df

    res = {}
    res["topology"] = read_topology(path_h5)
    res["k_means_specs"] = read_k_means_specs(path_h5)
    res["summary"] = read_summary(path_h5)
    loading_data_bar = st.progress(0, text="Loading energy balance")
    ebalance = read_energy_balance(path_h5)
    res["energybalance"] = process_k_means(
        ebalance, ["Period", "Node", "Carrier", "Variable"], res["k_means_specs"]
    )
    loading_data_bar.progress(20, text="Loading technology operation")
    technology_operation = read_technology_operation(path_h5)
    res["technology_operation"] = process_k_means(
        technology_operation,
        ["Period", "Node", "Technology", "Variable"],
        res["k_means_specs"],
    )
    loading_data_bar.progress(60, text="Loading technology design")
    res["technology_design"] = read_technology_design(path_h5)
    loading_data_bar.progress(80, text="Loading network operation and design")
    res["network_design"], network_operation = read_networks(path_h5)
    if network_operation:
        res["network_operation"] = process_k_means(
            network_operation,
            ["Period", "Network", "Arc_ID", "Variable", "FromNode", "ToNode"],
            res["k_means_specs"],
        )
    loading_data_bar.progress(100, text="Done")

    return res


def read_summary(path_h5):
    """
    Reads summary
    """
    with h5py.File(path_h5, "r") as hdf_file:
        summary = extract_datasets_from_h5_group(hdf_file["summary"])

    df_summary = pd.DataFrame(summary)

    return df_summary


def read_energy_balance(path_h5):
    """
    Reads energybalance
    """
    with h5py.File(path_h5, "r") as hdf_file:
        bal = extract_datasets_from_h5_group(hdf_file["operation/energy_balance"])

    return bal


def read_technology_operation(path_h5):
    """
    Reads technology operation
    """
    with h5py.File(path_h5, "r") as hdf_file:
        ope = extract_datasets_from_h5_group(hdf_file["operation/technology_operation"])
    return ope


def read_technology_design(path_h5):
    """
    Reads technology design
    """
    with h5py.File(path_h5, "r") as hdf_file:
        technology_design = extract_datasets_from_h5_group(hdf_file["design/nodes"])

    technology_design = pd.DataFrame(technology_design)
    technology_design = pd.melt(technology_design)
    technology_design.columns = ["Period", "Node", "Technology", "Variable", "Value"]

    return technology_design


def read_networks(path_h5):
    with h5py.File(path_h5, "r") as hdf_file:
        network_design = extract_datasets_from_h5_group(hdf_file["design/networks"])

    network_design = pd.DataFrame(network_design)
    if not network_design.empty:
        network_design = network_design.melt()
        network_design.columns = ["Period", "Network", "Arc_ID", "Variable", "Value"]
        network_design = network_design.pivot(
            columns="Variable", index=["Period", "Arc_ID", "Network"], values="Value"
        )
        network_design["FromNode"] = network_design["fromNode"].str.decode("utf-8")
        network_design["ToNode"] = network_design["toNode"].str.decode("utf-8")
        network_design.drop(columns=["fromNode", "toNode", "network"], inplace=True)
        network_design = network_design.reset_index()
        arc_ids = network_design[["Arc_ID", "FromNode", "ToNode"]]

    with h5py.File(path_h5, "r") as hdf_file:
        network_operation = extract_datasets_from_h5_group(
            hdf_file["operation/networks"]
        )
        # st.text(network_operation)

    if network_operation:
        network_operation = pd.DataFrame(network_operation)

        network_operation.columns.names = ["Period", "Network", "Arc_ID", "Variable"]

        network_operation = network_operation.T.reset_index()
        network_operation = pd.merge(
            network_operation,
            arc_ids.drop_duplicates(subset=["Arc_ID"]),
            how="inner",
            left_on="Arc_ID",
            right_on="Arc_ID",
        )
        network_operation = network_operation.set_index(
            ["Period", "Network", "Arc_ID", "Variable", "FromNode", "ToNode"]
        ).T

        network_operation = network_operation.to_dict(orient="list")
        ope = {}
        for key in network_operation:
            ope[key] = np.array(network_operation[key])
    else:
        ope = {}

    return network_design, ope


def read_topology(path_h5):

    topology = {}
    topology["nodes"] = load_nodes_from_h5_results(path_h5)
    topology["carriers"] = load_carriers_from_h5_results(path_h5)
    topology["periods"] = load_periods_from_h5_results(path_h5)

    return topology


def read_k_means_specs(path_h5):
    with h5py.File(path_h5, "r") as hdf_file:
        k_means_specs = extract_datasets_from_h5_group(hdf_file["k_means_specs"])

    return k_means_specs
