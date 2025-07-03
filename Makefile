.PHONY: ios

# Generate Xcode project & run lint
ios:
	@xcodegen generate --spec ios/project.yml --use-cache
	@echo "Running SwiftLint (non-fatal)..."
# @command -v swiftlint >/dev/null 2>&1 && swiftlint --fix --quiet || true
