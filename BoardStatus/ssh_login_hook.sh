# Auto-launch the board dashboard TUI on interactive SSH logins only, once
# per session (not for every subshell/tmux pane it opens), then drop to a
# normal shell when it exits (press q in the TUI).
board_dashboard() {
    python3 /home/arduino/ArduinoApps/board-status/board_dashboard.py
}

if [ -n "$SSH_CONNECTION" ] && [ -z "$BOARD_DASHBOARD_SHOWN" ]; then
    case "$-" in
        *i*)
            export BOARD_DASHBOARD_SHOWN=1
            board_dashboard || true
            clear
            echo "Dashboard closed -- back to your shell. Run 'board_dashboard' any time to reopen it."
            ;;
    esac
fi
