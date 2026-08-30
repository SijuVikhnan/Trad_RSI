import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# Set page configuration for a wider layout
st.set_page_config(page_title="NSE Live RSI Screener", layout="wide")

st.title("📈 NSE Live RSI & Smoothing MA Dashboard")
st.markdown("Upload your CSV watchlist to fetch live **RSI (14)** and **Smoothing MA (30)** from Yahoo Finance across multiple timeframes.")

# File uploader for the CSV
uploaded_file = st.file_uploader("Upload CSV watchlist (Must contain a 'Symbol' column with '.NS' suffix)", type=['csv'])

if uploaded_file:
    df_symbols = pd.read_csv(uploaded_file)
    
    # Check if 'Symbol' column exists
    if 'Symbol' not in df_symbols.columns:
        st.error("Error: Your CSV must contain a column named 'Symbol'.")
    else:
        symbols = df_symbols['Symbol'].dropna().tolist()
        
        # Define timeframes mapping yfinance intervals and lookback periods
        timeframes = {
            "1H": {"interval": "1h", "period": "2mo"},
            "3H": {"interval": "1h", "period": "3mo"}, # Fetched as 1H, resampled mathematically
            "1D": {"interval": "1d", "period": "1y"},
            "1W": {"interval": "1wk", "period": "2y"},
            "1M": {"interval": "1mo", "period": "5y"}
        }
        
        results = []
        
        with st.spinner("Fetching live market data and calculating indicators..."):
            for sym in symbols:
                # Initialize row data for the table
                row_data = {"Symbol": sym}
                
                for tf_name, tf_config in timeframes.items():
                    try:
                        # Fetch historical data
                        ticker = yf.Ticker(sym)
                        df = ticker.history(interval=tf_config["interval"], period=tf_config["period"])
                        
                        if df.empty:
                            row_data[f"RSI_{tf_name}"] = None
                            row_data[f"SMA30_{tf_name}"] = None
                            continue
                            
                        # Resample to 3H if calculating the 3-Hour timeframe
                        if tf_name == "3H":
                            # Resample data by grouping into 3-hour blocks
                            df = df.resample('3h').agg({
                                'Open': 'first', 
                                'High': 'max', 
                                'Low': 'min', 
                                'Close': 'last', 
                                'Volume': 'sum'
                            }).dropna()
                        
                        # Calculate Standard 14-period RSI
                        df['RSI_14'] = ta.rsi(df['Close'], length=14)
                        
                        # Calculate 30-period Simple Moving Average of the RSI
                        df['RSI_SMA_30'] = ta.sma(df['RSI_14'], length=30)
                        
                        # Extract the most recent (live) data points
                        latest_rsi = df['RSI_14'].iloc[-1]
                        latest_sma = df['RSI_SMA_30'].iloc[-1]
                        
                        # Store in row dictionary, rounded to 2 decimal places
                        row_data[f"RSI_{tf_name}"] = round(latest_rsi, 2) if pd.notna(latest_rsi) else "N/A"
                        row_data[f"SMA30_{tf_name}"] = round(latest_sma, 2) if pd.notna(latest_sma) else "N/A"
                        
                    except Exception as e:
                        row_data[f"RSI_{tf_name}"] = "Err"
                        row_data[f"SMA30_{tf_name}"] = "Err"
                
                results.append(row_data)
                
        # Convert results to a DataFrame and display it
        results_df = pd.DataFrame(results)
        st.success("Data fetching complete!")
        st.dataframe(results_df, use_container_width=True)
        
        # Add a refresh button for live market updates
        if st.button("Refresh Data"):
            st.rerun()