#chart showing rectified 2
import base64
import concurrent.futures
import numpy as np
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Set page configuration
st.set_page_config(page_title="NSE Live RSI Screener", layout="wide")

st.title("📈 Fast NSE Live RSI & Smoothing MA Dashboard")
st.markdown(
    "Upload your CSV watchlist to fetch live **RSI (14)** and **Smoothing MA"
    " (30)** from Yahoo Finance."
)


# Helper function to store Radar Chart data for lazy rendering
def prepare_radar_data(rsi_1m, rsi_1w, rsi_1d, rsi_1h, sma_1m, sma_1w, sma_1d, sma_1h):
  """Store chart data as tuple for caching - rendering happens on demand"""
  def clean(val):
    return (
        float(val)
        if pd.notna(val) and isinstance(val, (int, float, np.number))
        else 0.0
    )

  return (
      clean(rsi_1m), clean(rsi_1w), clean(rsi_1d), clean(rsi_1h),
      clean(sma_1m), clean(sma_1w), clean(sma_1d), clean(sma_1h),
  )


@st.cache_data(ttl=300, show_spinner=False)
def generate_radar_b64(radar_tuple, symbol=""):
  """Generate SVG on-demand with caching"""
  if not radar_tuple or len(radar_tuple) != 8:
    return ""
  
  rsi_1m, rsi_1w, rsi_1d, rsi_1h, sma_1m, sma_1w, sma_1d, sma_1h = radar_tuple
  categories = ["Month", "Week", "Day", "1 hour", "Month"]
  rsi_vals = [rsi_1m, rsi_1w, rsi_1d, rsi_1h, rsi_1m]
  sma_vals = [sma_1m, sma_1w, sma_1d, sma_1h, sma_1m]

  fig = go.Figure()

  # RSI (14) - Green dots and green lines
  fig.add_trace(
      go.Scatterpolar(
          r=rsi_vals,
          theta=categories,
          mode="lines+markers",
          name="RSI (14)",
          line=dict(color="green", width=2),
          marker=dict(color="green", size=8),
      )
  )

  # Smoothing MA (30) - Red dots and red lines
  fig.add_trace(
      go.Scatterpolar(
          r=sma_vals,
          theta=categories,
          mode="lines+markers",
          name="Smoothing MA (30)",
          line=dict(color="red", width=2),
          marker=dict(color="red", size=8),
      )
  )

  clean_symbol = symbol.replace(".NS", "") if symbol else ""
  
  fig.update_layout(
      title=dict(
          text="<u>" + clean_symbol + "</u>",
          x=0.05,
          xanchor="left",
          font=dict(
              size=14,
              family="Libre Franklin",
              color="black",
              style="italic",
              weight="bold"
          )
      ),
      polar=dict(
          radialaxis=dict(
              visible=True, range=[0, 100], tickvals=[0, 30, 50, 70, 100]
          )
      ),
      showlegend=True,
      legend=dict(
          orientation="h", yanchor="bottom", y=-0.4, xanchor="left", x=-0.15
                ),
      width=310,
      height=310,
      margin=dict(l=30, r=30, t=30, b=30),
      paper_bgcolor="rgba(3,109,239,0.2)",
      plot_bgcolor="rgba(3,109,239,0.2)",
  )

  try:
    img_bytes = fig.to_image(format="svg")
    b64_str = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_str}"
  except Exception:
    return ""


@st.cache_data(ttl=300, show_spinner=False)
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

  rsi_1w, sma_1w = row_data.get("RSI_1W"), row_data.get("SMA30_1W")
  weekly_call = (
      ("Weekly Long Call" if rsi_1w > sma_1w else "Weekly Short call")
      if pd.notna(rsi_1w) and pd.notna(sma_1w)
      else "Weekly Call: N/A"
  )

  rsi_1d, sma_1d = row_data.get("RSI_1D"), row_data.get("SMA30_1D")
  daily_call = (
      ("Daily Long call" if rsi_1d > sma_1d else "Daily Short Call")
      if pd.notna(rsi_1d) and pd.notna(sma_1d)
      else "Daily Call: N/A"
  )

  row_data["Weekly_Signal"] = weekly_call
  row_data["Daily_Signal"] = daily_call

  row_data["Radar_Data"] = prepare_radar_data(
      row_data.get("RSI_1M"),
      row_data.get("RSI_1W"),
      row_data.get("RSI_1D"),
      row_data.get("RSI_1H"),
      row_data.get("SMA30_1M"),
      row_data.get("SMA30_1W"),
      row_data.get("SMA30_1D"),
      row_data.get("SMA30_1H"),
  )

  return row_data


def style_signal(signal_text):
  if "Long" in str(signal_text):
    return (
        f'<span style="color: green; font-weight: bold;">{signal_text}</span>'
    )
  elif "Short" in str(signal_text):
    return f'<span style="color: red; font-weight: bold;">{signal_text}</span>'
  return f"<span>{signal_text}</span>"


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

    timeframes = {
        "1M": {"interval": "1mo", "period": "5y"},
        "1W": {"interval": "1wk", "period": "2y"},
        "1D": {"interval": "1d", "period": "6mo"},
        "1H": {"interval": "1h", "period": "2mo"},
    }

    results = []

    with st.spinner(
        f"Fetching data and generating charts for {len(symbols)} stocks..."
    ):
      with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_symbol = {
            executor.submit(process_ticker, sym, timeframes): sym
            for sym in symbols
        }

        for future in concurrent.futures.as_completed(future_to_symbol):
          results.append(future.result())

    results_df = (
        pd.DataFrame(results).sort_values(by="Symbol").reset_index(drop=True)
    )

    results_df.insert(0, "S.No", range(1, len(results_df) + 1))
    results_df.insert(2, "Radar Chart", "View Radar Chart")

    display_df = results_df.copy()

    hover_info = (
        results_df["Weekly_Signal"] + " | " + results_df["Daily_Signal"]
    )
    display_df["Symbol"] = [
        f'<span title="{info}" style="cursor: pointer; font-weight: bold;'
        f' text-decoration: underline dotted;">{sym}</span>'
        for sym, info in zip(results_df["Symbol"], hover_info)
    ]

    with st.spinner("Generating radar charts..."):
      radar_chart_html = []
      for radar_data, symbol in zip(results_df["Radar_Data"], results_df["Symbol"]):
        b64 = generate_radar_b64(radar_data, symbol)
        if b64:
          radar_chart_html.append(
              f'<div class="radar-tooltip">🔍 Radar Chart<div class="radar-popup"><img src="{b64}" width="300"/></div></div>'
          )
        else:
          radar_chart_html.append("N/A")
      
      display_df["Radar Chart"] = radar_chart_html

    display_df["Weekly_Signal"] = display_df["Weekly_Signal"].apply(style_signal)
    display_df["Daily_Signal"] = display_df["Daily_Signal"].apply(style_signal)

    st.success("Data fetching complete! Hover over Radar Chart links or Symbols.")

    # CSS for right-aligned hover popups inside table container
    st.markdown(
        """
        <style>
        .sticky-table-container {
            max-height: 600px;
            overflow-y: auto;
            overflow-x: visible;
            position: relative;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            
        }

        .sticky-table-container table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
	        margin-top: 2.5cm; /* 2.5 cm space above the container */
            margin-bottom: 2.5cm; /* 2.5 cm space below the container */
        }

        .sticky-table-container table th {
            position: sticky !important;
            top: 0 !important;
            background-color: #f8f9fa !important;
            color: #333333 !important;
            z-index: 100 !important;
            box-shadow: 0 2px 3px rgba(0,0,0,0.15) !important;
            padding: 8px 12px;
            border-bottom: 2px solid #dee2e6;
        }

        .sticky-table-container table td {
            padding: 8px 12px;
            border-bottom: 1px solid #e9ecef;
            position: relative;
        }

        .radar-tooltip {
            position: relative;
            display: inline-block;
            color: #0066cc;
            font-weight: bold;
            text-decoration: underline;
            cursor: pointer;
        }

        /* Displays popup to the right side of the link */
        .radar-tooltip .radar-popup {
            visibility: hidden;
            width: 320px;
            background-color: #ffffff;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 5px;
            position: absolute;
            z-index: 99999;
            left: 105%; /* Shift to right */
            top: 50%;
            transform: translateY(-50%); /* Vertically center aligned */
            box-shadow: 0px 4px 12px rgba(0,0,0,0.3);
            opacity: 0;
            transition: opacity 0.15s ease-in-out;
            pointer-events: none;
        }

        .radar-tooltip:hover .radar-popup {
            visibility: visible;
            opacity: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    display_cols = [
        "S.No",
        "Symbol",
        "Radar Chart",
        "Weekly_Signal",
        "Daily_Signal",
        "RSI_1M",
        "SMA30_1M",
        "RSI_1W",
        "SMA30_1W",
        "RSI_1D",
        "SMA30_1D",
        "RSI_1H",
        "SMA30_1H",
    ]

    raw_html_table = display_df[display_cols].to_html(escape=False, index=False)

    st.write(
        f'<div class="sticky-table-container">{raw_html_table}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
      if st.button("🔄 Refresh Data"):
        st.rerun()

    with col2:
      if st.button("🧹 Clear Cache"):
        st.cache_data.clear()
        st.rerun()

    with col3:
      csv_export_df = results_df.copy()
      if "Radar_Data" in csv_export_df.columns:
        csv_export_df = csv_export_df.drop(columns=["Radar_Data"])
      
      csv_data = csv_export_df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Download Results as CSV",
          data=csv_data,
          file_name="rsi_screener_results.csv",
          mime="text/csv",
      )