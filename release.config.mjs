let dryRun = (process.env.RELEASE_DRY_RUN || "false").toLowerCase() === "true";

// The backend is deployed, not published: pyproject.toml has package-mode =
// false, so there is nothing to build or upload to PyPI. A release is a git tag,
// a GitHub release and the version recorded in pyproject.toml and CHANGELOG.md.
// `poetry version` works in non-package mode too.
let prepareCmd = "poetry version -- \${nextRelease.version}";

import config from 'semantic-release-preconfigured-conventional-commits' with {type: 'json'};

config.plugins.push(
    ["@semantic-release/exec", {
        "prepareCmd" : prepareCmd,
    }]
)

if (!dryRun) {
    config.plugins.push(
        "@semantic-release/github",
        ["@semantic-release/git", {
            "assets": [
                "CHANGELOG.md",
                "pyproject.toml"
            ],
            "message": "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
        }]
    );
}

export default config;
