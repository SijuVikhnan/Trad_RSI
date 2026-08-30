import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import concurrent.futures

# Set page configuration
st.set_page_config(page_title="NSE Live RSI Screener", layout="wide")

st.title("📈 Fast NSE Live RSI & Smoothing MA Dashboard")
st.markdown("Upload your CSV watchlist to fetch live **RSI (14)** and **Smoothing MA (30)** from Yahoo Finance.")

# Helper function to process a single ticker
def process_ticker(sym, timeframes):
    row_data = {"Symbol": sym}
    for tf_name, tf_config in timeframes.items():
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(interval=tf_config["interval"], period=tf_config["period"])
            
            if df.empty:
                row_data[f"RSI_{tf_name}"] = None
                row_data[f"SMA30_{tf_name}"] = None
                continue
                
            if tf_name == "3H":
                df = df.resample('3h').agg({
                    'Open': 'first', 'High': 'max', 
                    'Low': 'min', 'Close': 'last', 'Volume': 'sum'
                }).dropna()
            
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
            df['RSI_SMA_30'] = ta.sma(df['RSI_14'], length=30)
            
            latest_rsi = df['RSI_14'].iloc[-1]
            latest_sma = df['RSI_SMA_30'].iloc[-1]
            
            row_data[f"RSI_{tf_name}"] = round(latest_rsi, 2) if pd.notna(latest_rsi) else None
            row_data[f"SMA30_{tf_name}"] = round(latest_sma, 2) if pd.notna(latest_sma) else None
            
        except Exception:
            row_data[f"RSI_{tf_name}"] = None
            row_data[f"SMA30_{tf_name}"] = None
            
    return row_data

# File uploader
uploaded_file = st.file_uploader("Upload CSV watchlist (Must contain a 'Symbol' column with '.NS')", type=['csv'])

if uploaded_file:
    df_symbols = pd.read_csv(uploaded_file)
    
    if 'Symbol' not in df_symbols.columns:
        st.error("Error: Your CSV must contain a column named 'Symbol'.")
    else:
        symbols = df_symbols['Symbol'].dropna().tolist()
        
        # Timeframes configuration
        timeframes = {
            "1H": {"interval": "1h", "period": "2mo"},
            "3H": {"interval": "1h", "period": "3mo"},
            "1D": {"interval": "1d", "period": "6mo"}, # Reduced period to save memory and speed
            "1W": {"interval": "1wk", "period": "2y"},
            "1M": {"interval": "1mo", "period": "5y"}
        }
        
        results = []
        
        with st.spinner(f"Fetching data for {len(symbols)} stocks using Multithreading..."):
            # Set up Multithreading
            # max_workers=20 means it will process 20 stocks at the exact same time
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                # Map the process_ticker function to all symbols
                future_to_symbol = {executor.submit(process_ticker, sym, timeframes): sym for sym in symbols}
                
                # Gather the results as they finish
                for future in concurrent.futures.as_completed(future_to_symbol):
                    results.append(future.result())
                
        # Convert results to a DataFrame and sort alphabetically by Symbol
        results_df = pd.DataFrame(results).sort_values(by="Symbol").reset_index(drop=True)
        
        st.success("Data fetching complete!")
        st.dataframe(results_df, use_container_width=True)
        
        if st.button("Refresh Data"):
            st.rerun()