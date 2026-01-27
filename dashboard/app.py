"""
TuffWraps Marketing Attribution Dashboard

Daily decision dashboard for CAM-based marketing optimization.
"""

# CRITICAL: Setup paths before ANY other imports
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent
PAGES_DIR = DASHBOARD_DIR / "pages"

# Force path to be first
sys.path = [str(DASHBOARD_DIR)] + [p for p in sys.path if p != str(DASHBOARD_DIR)]

# Now safe to import everything else
import streamlit as st
import importlib.util

st.set_page_config(
    page_title="TuffWraps Attribution",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .positive { color: #10B981; }
    .negative { color: #EF4444; }
    .neutral { color: #6B7280; }
</style>
""", unsafe_allow_html=True)


def load_page_module(page_name: str):
    """Load a page module by name using importlib."""
    page_path = PAGES_DIR / f"{page_name}.py"
    spec = importlib.util.spec_from_file_location(page_name, page_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[page_name] = module
    spec.loader.exec_module(module)
    return module


def main():
    st.sidebar.title("TuffWraps Attribution")

    page = st.sidebar.radio(
        "Navigate",
        [
            "⚡ Action Board",
            "📊 Command Center",
            "🤖 AI Assistant",
            "📝 Activity Log",
            "💰 CAM Performance",
            "🎯 TOF Analysis",
            "📋 Campaign Manager",
            "🔍 Data Explorer",
        ],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Last Updated**")
    st.sidebar.markdown("Data pulls daily at 8:00 AM EST")

    # Map pages to module names
    page_map = {
        "⚡ Action Board": "action_board",
        "📊 Command Center": "command_center",
        "🤖 AI Assistant": "ai_chat",
        "📝 Activity Log": "activity_log",
        "💰 CAM Performance": "cam_performance",
        "🎯 TOF Analysis": "tof_analysis",
        "📋 Campaign Manager": "campaign_manager",
        "🔍 Data Explorer": "data_explorer",
    }

    module_name = page_map.get(page)
    if module_name:
        module = load_page_module(module_name)
        module.render()


if __name__ == "__main__":
    main()
