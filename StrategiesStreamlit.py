import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import hashlib
import time
import base64
import os
import re


# Environment variables for credentials
USER_ID = '92090'
API_TOKEN = '7df20f89e389d894c09528956e8bbd1c8a76946c12d56dd8624a6705825243ef'

# Define API endpoints
url_readBacktest = "https://www.quantconnect.com/api/v2/backtests/read"
url_readProject = "https://www.quantconnect.com/api/v2/projects/read"
url_listProjectBacktest = "https://www.quantconnect.com/api/v2/backtests/list"

monthly_project_IDs = [19333694]  # 19357714
OTHER_PROJECT_IDS = [19395255]

# Intraday
project_IDs = [19014068, 19015686, 19016182, 19016331, 19025603, 19015442, 19087390, 19087500, 19095659, 
               19113130, 19134299, 19359592]

project_IDs = project_IDs + monthly_project_IDs + OTHER_PROJECT_IDS



# 19025674 - QP_317TradingFOMCAnnouncementswithSummaryofEconomicProjections - Only working for 2019 - may be data missing in attached file
# 19113130 - BenchMark SPY
# 19085479 - Issue it it requires 1 mln so messes up the charts - its 1025 -MeanReversionIntradayStrategy

project_names_map = {} # Global variable for project names



# Function to create headers with appropriate authentication
def get_authenticated_headers():
    timestamp = str(int(time.time()))
    data_string = f"{API_TOKEN}:{timestamp}"
    hashed_token = hashlib.sha256(data_string.encode('utf-8')).hexdigest()
    auth_string = f"{USER_ID}:{hashed_token}"
    api_token = base64.b64encode(auth_string.encode('utf-8')).decode('ascii')
    return {
        'Authorization': f'Basic {api_token}',
        'Timestamp': timestamp
    }


# https://www.quantconnect.com/docs/v2/cloud-platform/api-reference/backtest-management/list-backtests
def list_backtests(project_id):
    response = requests.post(url_listProjectBacktest, headers=get_authenticated_headers(), data={'projectId': project_id, 'includeStatistics': True})
    if response.status_code == 200:
        return response.json().get('backtests', [])
    else:
        print("Failed to list backtests:", response.status_code, response.text)
        return []


def fetch_project_details(project_id):
    headers = get_authenticated_headers()
    response = requests.post(url_readProject, headers=headers, data={'projectId': project_id})
    if response.status_code == 200:
        return response.json()['projects'][0]
    else:
        print("Failed to retrieve project details:", response.status_code, response.text)
        return None

def fetch_backtest_result(project_id, backtest_id, key=None):
    headers = get_authenticated_headers()
    response = requests.post(url_readBacktest, headers=headers, data={'projectId': project_id, 'backtestId': backtest_id})
    if response.status_code == 200:
        try:
            json_response = response.json()
            if 'backtest' in json_response:
                if key is not None:
                    return json_response['backtest'][key]
                else:
                    return json_response['backtest']
            else:
                print(f"No 'backtest' key in JSON response. Full response: {json_response}")
                return {}
        except ValueError:
            print(f"Failed to decode JSON from response. Status Code: {response.status_code}, Response Text: {response.text}")
            return {}
        except KeyError as e:
            print(f"Key error: {e}. Invalid key in JSON response. Full response: {json_response}")
            return {}
    else:
        print("Failed to retrieve backtest results:", response.status_code, response.text)
        return {}

def create_project_name_mapping(project_ids):
    project_details = {ID: fetch_project_details(ID) for ID in project_ids}
    project_names_short = {ID: re.findall(r'\d+', details['name'])[0] if details and 'name' in details else 'Unknown' for ID, details in project_details.items()}
    return project_names_short

# def create_short_to_full_name_mapping(project_ids):
#     # Fetch project details for each project ID
#     project_details = {ID: fetch_project_details(ID) for ID in project_ids}
#     # Create a mapping of short names (numeric part) to full project names
#     short_to_full_name_map = {re.findall(r'\d+', details['name'])[0]: details['name'][3+len(re.findall(r'\d+', details['name'])[0]):].strip()
#                               if details and 'name' in details else 'Unknown'
#                               for ID, details in project_details.items()}
#     return short_to_full_name_map


def create_short_to_full_name_mapping(project_ids):
    # Fetch project details for each project ID
    project_details = {ID: fetch_project_details(ID) for ID in project_ids}
    # Create a mapping of short names (numeric part) to full project names and include the original project ID
    short_to_full_name_map = {
        re.findall(r'\d+', details['name'])[0]: (details['name'][3+len(re.findall(r'\d+', details['name'])[0]):].strip(), ID)
        if details and 'name' in details else ('Unknown', ID)
        for ID, details in project_details.items()
    }
    return short_to_full_name_map



def process_data(backtest_period):
    global project_names_map
    
    project_names_map = create_short_to_full_name_mapping(project_IDs)
    project_names_short = create_project_name_mapping(project_IDs)
    
    backtest_metrics = ['alpha',  'beta', 'compoundingAnnualReturn', 'drawdown', 'lossRate', 'netProfit', 'parameters', 'psr', 'sortinoRatio', 'trades' ,'treynorRatio', 'winRate','backtestId'] 

    # Fetch and organize strategy details
    # strategy_dict = {ID: next((bkt for bkt in list_backtests(ID) if bkt['name'] == backtest_period), None) for ID in project_IDs}
    strategy_dict = {ID: next((bkt for bkt in list_backtests(ID) if bkt['name'] == backtest_period), None) for ID in project_IDs}
    # Print missing project IDs in Streamlit
    # st.write(f"No data found for project IDs: {', '.join([str(ID) for ID in project_IDs if not strategy_dict.get(ID)])}")
    missing_IDs = [str(ID) for ID in project_IDs if not strategy_dict.get(ID)]
    if missing_IDs:
        st.write(f"No data found for project IDs: {', '.join(missing_IDs)}")


    strategy_dict = {k: v for k, v in strategy_dict.items() if v is not None}  # Exclude None entries

    df_metrics = pd.DataFrame({k: {m: v[m] for m in backtest_metrics if m in v} for k, v in strategy_dict.items()}).transpose()

    strategy_dict       = {}
    strategy_equity_dict = {}
    strategy_return_dict = {}
    strategy_trades_dict = {}

    # Processing detailed backtest results only if data is available
    for projectID, row in df_metrics.iterrows():
        backtest_result = fetch_backtest_result(project_id=projectID, backtest_id=row['backtestId'], key=None)

        strategy_dict[projectID] = backtest_result # reusing this name as earlier sent to df_metrics
        
        # Creating DataFrame for equity curve
        equity_values = backtest_result['charts']['Strategy Equity']['series']['Equity']['values']
        equity_df = pd.DataFrame(equity_values, columns=['Timestamp', 'Open', 'High', 'Low', 'Close'])
        equity_df.index = pd.to_datetime(equity_df['Timestamp'], unit='s')
        equity_df.drop(columns=['Timestamp', 'Open', 'High', 'Low'], inplace=True)
        strategy_equity_dict[projectID] = equity_df
        
        # Creating DataFrame for returns curve
        return_values = backtest_result['charts']['Strategy Equity']['series']['Return']['values']
        return_df = pd.DataFrame(return_values, columns=['Timestamp', 'Return'])
        return_df.index = pd.to_datetime(return_df['Timestamp'], unit='s')
        return_df.drop(columns=['Timestamp'], inplace=True)
        strategy_return_dict[projectID] = return_df

        # Extracting trade data - contains data/metric for each trade Individually
        trades = backtest_result['totalPerformance']['closedTrades']
        trade_df = pd.DataFrame([{
            **{f'symbol_{k}': v for k, v in trade.get('symbol', {}).items()}, 
            **{k: v for k, v in trade.items() if k not in ['symbol', 'direction', 'symbol_value', 'symbol_id']}
        } for trade in trades])
        strategy_trades_dict[projectID] = trade_df


    # This has all the Metrics from nested keys in strategy_dict (the one in the loop)
    df = pd.DataFrame({
        ID: {
            **v['statistics'], 
            **v['totalPerformance']['tradeStatistics'],
            **v['totalPerformance']['portfolioStatistics'], 
            **v['runtimeStatistics']
        }
        for ID, v in strategy_dict.items()
    }).transpose()  # Transpose to make each project ID a row

    # For deciphering which column came from which source: - Not using
    first_key = next(iter(strategy_dict))
    metrics_Index = {
        'backtestList': list(df_metrics.columns),
        'statistics': list(strategy_dict[first_key]['statistics'].keys()),
        'tradeStatistics': list(strategy_dict[first_key]['totalPerformance']['tradeStatistics'].keys()),
        'portfolioStatistics': list(strategy_dict[first_key]['totalPerformance']['portfolioStatistics'].keys()),
        'runtimeStatistics': list(strategy_dict[first_key]['runtimeStatistics'].keys())
    }

    df.index.name = 'ProjectID'

    final_df = pd.concat([df_metrics, df], axis=1)
    final_df = final_df.T
    
    # project_names = {ID: fetch_project_details(ID)['name'][3:] for ID in final_df.columns}
    # final_df.columns = [project_names.get(ID, ID) for ID in final_df.columns]
    
    final_df.columns = [project_names_short[ID] for ID in final_df.columns]

    mask_first = final_df.index.isin(['winRate', 'lossRate', 'sortinoRatio', 'beta', 'alpha', 'treynorRatio']) & final_df.index.duplicated(keep='last')
    mask_second = ~final_df.index.isin(['winRate', 'lossRate', 'sortinoRatio', 'beta', 'alpha', 'treynorRatio']) & final_df.index.duplicated(keep='first')
    final_df = final_df[~(mask_first | mask_second)]

    # return strategy_dict, strategy_equity_dict, strategy_return_dict, strategy_trades_dict, final_df
    return strategy_equity_dict, final_df


def create_equity_df(strategy_equity_dict, project_IDs):

    strategy_equity_df = pd.concat({projectID: df['Close'] for projectID, df in strategy_equity_dict.items()},axis=1)
    project_names = {ID: fetch_project_details(ID)['name'][3:] for ID in strategy_equity_df.columns}
    strategy_equity_df.columns = [project_names.get(ID, ID) for ID in strategy_equity_df.columns]
    strategy_equity_df.sort_index(inplace=True)
    strategy_equity_df.ffill(inplace=True)

    return strategy_equity_df


def main():
    st.set_page_config(layout="wide")  # Set page config at the beginning of the function
    st.title("Strategies Dashboard")


    # Dropdown for selecting the backtest period
    backtest_periods = ['YTD', '5YR', '2023']
    selected_backtest_period = st.selectbox("Select Backtest Period", options=backtest_periods)

    # Process data based on selected period
    # strategy_dict, strategy_equity_dict, strategy_return_dict, strategy_trades_dict, final_df = process_data(selected_backtest_period)
    strategy_equity_dict, final_df = process_data(selected_backtest_period)
    strategy_equity_df = create_equity_df(strategy_equity_dict, project_IDs)
    
    strategy_equity_df.columns = [re.findall(r'\d+', col)[0] if re.findall(r'\d+', col) else 'Unknown' for col in strategy_equity_df.columns]
    
    if selected_backtest_period == '5YR':
        # select starting from 2019
        strategy_equity_df = strategy_equity_df.loc['2019-01-01':]

    elif selected_backtest_period == '2023':
        strategy_equity_df = strategy_equity_df.loc['2023-01-01':]
    
    elif selected_backtest_period == 'YTD':
        strategy_equity_df = strategy_equity_df.loc['2024-01-01':]


    fig = px.line(strategy_equity_df, x=strategy_equity_df.index, y=strategy_equity_df.columns, title='Equity Curve')
    st.plotly_chart(fig, use_container_width=True)  # Use the full width of the container

    # Display the final DataFrame
    if not final_df.empty:
        st.write("Strategy Metrics Table:")
        st.dataframe(final_df, height=600,use_container_width=True)  # Adjust the height based on your preference
    else:
        st.write("No data available to display.")

    st.write("Strategy Keys:")
    # df = pd.DataFrame(list(project_names_map.items()), columns=['ID', 'Strategy Name'])
    # df.index = df.index + 1
    # st.table(df)
    df = pd.DataFrame([(key, name_id[0], name_id[1]) for key, name_id in project_names_map.items()], 
                      columns=['Key', 'Strategy Name', 'QuantConnect ID'])
    df.index = df.index + 1
    st.table(df)


if __name__ == "__main__":
    main()