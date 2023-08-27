from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import plotly.express as px
app = Flask(__name__)

# Load your dataset (replace with your actual data source)
df = pd.read_csv('data.csv')


def calculate_MED_MAD(data):
    median = data.median()
    mad = np.median(np.abs(data - median))
    return (median, mad)


def calculate_bounds(data, z_scores, lower_threshold, upper_threshold):
    median, mad = calculate_MED_MAD(data)
    upper_bounds = []
    lower_bounds = []
    for i in range(len(z_scores)):
        upper_bound = median + (mad * z_scores[i] * lower_threshold)
        lower_bound = median - (mad * z_scores[i] * upper_threshold)
        upper_bounds.append(upper_bound)
        lower_bounds.append(lower_bound)
    return lower_bounds, upper_bounds


def calculate_zscore(df, data, lower_threshold, upper_threshold):
    median, mad = calculate_MED_MAD(data)
    z_scores = (np.abs((data - median) / mad))
    df['z_score'] = z_scores
    z_scores = z_scores.tolist()
    df['lower_bound'], df['upper_bound'] = calculate_bounds(data, z_scores, lower_threshold, upper_threshold)
    df['anomaly'] = np.where((df['y'] > df['upper_bound']) | (df['y'] < df['lower_bound']), 1, 0)
    return df


# Define upper and lower anomaly thresholds (replace with your values)
upper_threshold = 1
lower_threshold = 0.5


def detect_anomalies(df):
    return calculate_zscore(df, df['y'], lower_threshold, upper_threshold)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_anomaly_data')
def get_anomaly_data():
    # Assuming your dataset has 'ds', 'y', and 'anomaly' columns
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date and end_date:
        filtered_data = df[(df['ds'] >= start_date) & (df['ds'] <= end_date)]
        data_with_anomalies = detect_anomalies(filtered_data)
        anomaly_data = data_with_anomalies[['ds', 'y', 'anomaly', 'lower_bound', 'upper_bound']].to_dict(
            orient='records')
        return jsonify(anomaly_data)
    else:
        return jsonify([])


if __name__ == '__main__':
    # data = calculate_zscore(data['y'], lower_threshold, upper_threshold)
    data = detect_anomalies(df)
    app.run(debug=True)
