.PHONY: help install-plist uninstall-plist reload-plist status-plist

LABEL        := com.dc-bot.local-discord-bot
PLIST_TPL    := $(LABEL).plist.template
PLIST_DEST   := $(HOME)/Library/LaunchAgents/$(LABEL).plist
UV_PATH      := $(shell command -v uv)
UV_DIR       := $(shell dirname $(UV_PATH) 2>/dev/null)
PROJECT_DIR  := $(shell pwd)

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install-plist: ## Generate LaunchAgent plist and load it via launchctl
	@if [ -z "$(UV_PATH)" ]; then echo "error: uv not found in PATH"; exit 1; fi
	@mkdir -p logs
	@mkdir -p "$(HOME)/Library/LaunchAgents"
	@sed \
		-e "s|\$${UV_PATH}|$(UV_PATH)|g" \
		-e "s|\$${UV_DIR}|$(UV_DIR)|g" \
		-e "s|\$${PROJECT_DIR}|$(PROJECT_DIR)|g" \
		$(PLIST_TPL) > $(PLIST_DEST)
	@launchctl bootout gui/$$(id -u) $(PLIST_DEST) 2>/dev/null || true
	@launchctl bootstrap gui/$$(id -u) $(PLIST_DEST)
	@echo "installed: $(LABEL)"
	@echo "logs:      $(PROJECT_DIR)/logs/bot.log"

uninstall-plist: ## Stop and remove the installed LaunchAgent plist
	@launchctl bootout gui/$$(id -u) $(PLIST_DEST) 2>/dev/null || true
	@rm -f $(PLIST_DEST)
	@echo "uninstalled: $(LABEL)"

reload-plist: uninstall-plist install-plist ## Reinstall after editing the template

status-plist: ## Show launchctl status and tail the most recent log
	@launchctl print gui/$$(id -u)/$(LABEL) 2>&1 | head -n 25 || echo "not loaded"
	@echo "--- last 20 lines of logs/bot.log ---"
	@tail -n 20 logs/bot.log 2>/dev/null || echo "(no log yet)"
