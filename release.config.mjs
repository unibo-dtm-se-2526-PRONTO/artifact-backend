let dryRun = (process.env.RELEASE_DRY_RUN || "false").toLowerCase() === "true";
let testPypi = (process.env.RELEASE_TEST_PYPI || "false").toLowerCase() === "true";

// A release records the new version in pyproject.toml (`poetry version`), then
// builds the package and uploads it to PyPI, or to TestPyPI (the repository
// declared in poetry.toml) while RELEASE_TEST_PYPI is true. Poetry reads the
// token from POETRY_PYPI_TOKEN_PYPI or POETRY_PYPI_TOKEN_TESTPYPI (deploy.yml),
// so it never appears in a command.
let prepareCmd = "poetry version -- \${nextRelease.version}";
let publishCmd = "poetry publish --build";

if (testPypi) {
    publishCmd += " --repository testpypi";
}

if (dryRun) {
    publishCmd += " --dry-run";
}

import config from 'semantic-release-preconfigured-conventional-commits' with {type: 'json'};

config.plugins.push(
    ["@semantic-release/exec", {
        "prepareCmd" : prepareCmd,
        "publishCmd": publishCmd,
    }]
)

if (!dryRun) {
    config.plugins.push(
        ["@semantic-release/github", {
            "assets": [
                { "path": "dist/*" },
            ]
        }],
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
