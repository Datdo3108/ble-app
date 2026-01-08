import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

label_list = ['1',
              '2',
              '3',
              '4',
              ]

def read_time_series_data(file_path, time_column='Time', percent_column='Percent'):
    """
    Reads time series data from a CSV file.

    :param file_path: Path to the CSV file.
    :param time_column: Name of the time column.
    :param percent_column: Name of the percent column.
    :return: pandas DataFrame with time and percent columns.
    """
    try:
        df = pd.read_csv(file_path)
        
        # Extract time and percent columns
        time_series = df[time_column] - df[time_column].iloc[0]
        percent_series = df[percent_column].astype(str).str.replace('%', '').astype(float)
        
        return time_series, percent_series
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None

def plot_time_series(data_dict, title='Time Series Data Plot', xlabel='Time', ylabel='Percentage (%)'):
    """
    Plots time series data from multiple files.

    :param data_dict: Dictionary where keys are labels and values are tuples of (time, percent) data.
    :param title: Title of the plot.
    :param xlabel: Label for the X-axis.
    :param ylabel: Label for the Y-axis.
    """
    plt.figure(figsize=(10, 6))
    
    i = 0
    for label, (time_data, percent_data) in data_dict.items():
        label = label_list[i]
        plt.plot(time_data, percent_data, label=label)
        i += 1
    
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def main():
    # Specify the folder path
    folder_path = r'5-11\multiple graph'  # Replace with your folder path

    # Specify the file pattern (e.g., '*.csv' for CSV files)
    file_pattern = os.path.join(folder_path, '*.csv')  # Adjust the extension if needed

    # Get list of all matching files
    file_list = glob.glob(file_pattern)

    if not file_list:
        print("No files found in the specified folder.")
        return

    # Dictionary to hold data from each file
    data_dict = {}

    for file_path in file_list:
        # Extract the file name without extension for labeling
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        print(file_name)
        
        # Read time series data (modify 'time_column' and 'percent_column' if needed)
        time_data, percent_data = read_time_series_data(file_path, time_column='Time', percent_column='Percent')
        
        if time_data is not None and percent_data is not None:
            data_dict[file_name] = (time_data, percent_data)
        else:
            print(f"Skipping file {file_path} due to read errors.")

    if not data_dict:
        print("No valid data to plot.")
        return

    # Plot the data
    plot_time_series(data_dict, title='Biểu đồ đáp ứng nhiệt độ theo thời gian', xlabel='Thời gian (s)', ylabel='Phần trăm (%)')

if __name__ == "__main__":
    main()
