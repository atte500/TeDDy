.PHONY: commit probe

commit:
	@[ -n "$(MESSAGE)" ] || { echo "Usage: make commit MESSAGE='<type>(<scope>): <description>' [NO_VERIFY=1]"; exit 1; }; \
	git add .; \
	pre-commit run || true; \
	git add .; \
	git commit -m "$(MESSAGE)" $(if $(NO_VERIFY),--no-verify,); \
	git pull --rebase && git push || [ -z "$$(git remote)" ]

probe:
	@args="$(filter-out $@,$(MAKECMDGOALS))"; \
	[ -n "$$args" ] || { echo "Usage: make probe '<reason>'"; exit 1; }; \
	git add -f spikes/debug/remote_probe.sh; \
	git commit -m 'debug: probe' --no-verify; \
	git push; \
	gh workflow run debug.yml --field reason="$$args"; \
	sleep 10; \
	RUN_ID=$$(gh run list -w debug.yml -L 1 --json databaseId -q '.[0].databaseId'); \
	gh run watch $$RUN_ID; \
	gh run view $$RUN_ID --log

%:
	@:
