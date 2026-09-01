import concurrent.futures
import numpy as np
import pandas as pd
import pandas_ta as ta
import streamlit as st
import yfinance as yf

# Set page configuration
st.set_page_config(page_title="NSE Live RSI Screener", layout="wide")

st.title("📈 Fast NSE Live RSI & Smoothing MA Dashboard")
st.markdown(
    "Upload your CSV watchlist to fetch live **RSI (14)** and **Smoothing MA"
    " (30)** from Yahoo Finance."
)


# Helper function to process a single ticker
def process_ticker(sym, timeframes):
  row_data = {"Symbol": sym}
  for tf_name, tf_config in timeframes.items():
    try:
      ticker = yf.Ticker(sym)
      df = ticker.history(
          interval=tf_config["interval"], period=tf_config["period"]
      )

      if df.empty:
        row_data[f"RSI_{tf_name}"] = np.nan
        row_data[f"SMA30_{tf_name}"] = np.nan
        continue

      df["RSI_14"] = ta.rsi(df["Close"], length=14)
      df["RSI_SMA_30"] = ta.sma(df["RSI_14"], length=30)

      latest_rsi = df["RSI_14"].iloc[-1]
      latest_sma = df["RSI_SMA_30"].iloc[-1]

      row_data[f"RSI_{tf_name}"] = (
          round(latest_rsi, 2) if pd.notna(latest_rsi) else np.nan
      )
      row_data[f"SMA30_{tf_name}"] = (
          round(latest_sma, 2) if pd.notna(latest_sma) else np.nan
      )

    except Exception:
      row_data[f"RSI_{tf_name}"] = np.nan
      row_data[f"SMA30_{tf_name}"] = np.nan

  # Evaluate Weekly Signal
  rsi_1w = row_data.get("RSI_1W")
  sma_1w = row_data.get("SMA30_1W")
  if pd.notna(rsi_1w) and pd.notna(sma_1w):
    weekly_call = "Weekly Long Call" if rsi_1w > sma_1w else "Weekly Short call"
  else:
    weekly_call = "Weekly Call: N/A"

  # Evaluate Daily Signal
  rsi_1d = row_data.get("RSI_1D")
  sma_1d = row_data.get("SMA30_1D")
  if pd.notna(rsi_1d) and pd.notna(sma_1d):
    daily_call = "Daily Long call" if rsi_1d > sma_1d else "Daily Short Call"
  else:
    daily_call = "Daily Call: N/A"

  row_data["Weekly_Signal"] = weekly_call
  row_data["Daily_Signal"] = daily_call

  return row_data


# Helper function to format signal text with color and bolding
def style_signal(signal_text):
  if "Long" in str(signal_text):
    return (
        f'<span style="color: green; font-weight: bold;">{signal_text}</span>'
    )
  elif "Short" in str(signal_text):
    return f'<span style="color: red; font-weight: bold;">{signal_text}</span>'
  return f"<span>{signal_text}</span>"


# File uploader
uploaded_file = st.file_uploader(
    "Upload CSV watchlist (Must contain a 'Symbol' column with '.NS')",
    type=["csv"],
)

if uploaded_file:
  df_symbols = pd.read_csv(uploaded_file)

  if "Symbol" not in df_symbols.columns:
    st.error("Error: Your CSV must contain a column named 'Symbol'.")
  else:
    symbols = df_symbols["Symbol"].dropna().tolist()

    # Timeframes configuration (Monthly, Weekly, Daily)
    timeframes = {
        "1M": {"interval": "1mo", "period": "5y"},
        "1W": {"interval": "1wk", "period": "2y"},
        "1D": {"interval": "1d", "period": "6mo"},
    }

    results = []

    with st.spinner(
        f"Fetching data for {len(symbols)} stocks using Multithreading..."
    ):
      with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_symbol = {
            executor.submit(process_ticker, sym, timeframes): sym
            for sym in symbols
        }

        for future in concurrent.futures.as_completed(future_to_symbol):
          results.append(future.result())

    # Convert results to a DataFrame and sort alphabetically by Symbol
    results_df = (
        pd.DataFrame(results).sort_values(by="Symbol").reset_index(drop=True)
    )

    # 1. Add Serial Number (S.No) column at index 0
    results_df.insert(0, "S.No", range(1, len(results_df) + 1))

    # Create a display copy for HTML rendering
    display_df = results_df.copy()

    # 2. Add styled hover text to Symbol
    hover_info = results_df["Weekly_Signal"] + " | " + results_df["Daily_Signal"]
    display_df["Symbol"] = [
        f'<span title="{info}" style="cursor: pointer; font-weight: bold;'
        f' text-decoration: underline dotted;">{sym}</span>'
        for sym, info in zip(results_df["Symbol"], hover_info)
    ]

    # 3. Apply bold green for Long Calls and bold red for Short Calls
    display_df["Weekly_Signal"] = display_df["Weekly_Signal"].apply(
        style_signal
    )
    display_df["Daily_Signal"] = display_df["Daily_Signal"].apply(style_signal)

    st.success("Data fetching complete! Hover over any Symbol to see signals.")

    # Render formatted HTML Table
    display_cols = [
        "S.No",
        "Symbol",
        "Weekly_Signal",
        "Daily_Signal",
        "RSI_1M",
        "SMA30_1M",
        "RSI_1W",
        "SMA30_1W",
        "RSI_1D",
        "SMA30_1D",
    ]

    st.write(
        display_df[display_cols].to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Layout buttons side-by-side
    col1, col2 = st.columns([1, 4])

    with col1:
      if st.button("Refresh Data"):
        st.rerun()

    with col2:
      # Export clean CSV (including S.No, excluding HTML tags)
      csv_data = results_df[display_cols].to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Download Results as CSV",
          data=csv_data,
          file_name="rsi_screener_results.csv",
          mime="text/csv",
      )