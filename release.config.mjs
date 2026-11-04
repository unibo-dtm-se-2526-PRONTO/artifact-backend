let dryRun = (process.env.RELEASE_DRY_RUN || "false").toLowerCase() === "true";
let pypi = (process.env.RELEASE_PYPI || "false").toLowerCase() === "true";
let image = "ghcr.io/unibo-dtm-se-2526-pronto/pronto-helpdesk";

// A release records the new version in pyproject.toml (`poetry version`) and
// uploads the package to TestPyPI (the repository declared in poetry.toml);
// if that succeeds and RELEASE_PYPI is true, it uploads the same files in dist/
// to PyPI. Then it builds the Docker image and pushes it to GHCR as <version>
// and latest. Poetry reads the tokens from POETRY_PYPI_TOKEN_TESTPYPI and
// POETRY_PYPI_TOKEN_PYPI (deploy.yml), so they never appear in a command.
let prepareCmd = "poetry version -- \${nextRelease.version}";
let dryRunFlag = dryRun ? " --dry-run" : "";
let publishCmd = "poetry publish --build --repository testpypi" + dryRunFlag;

if (pypi) {
    publishCmd += " && poetry publish" + dryRunFlag;
}

// The label links the package on GHCR to this repository.
publishCmd += " && docker build"
    + " --label org.opencontainers.image.source=https://github.com/unibo-dtm-se-2526-PRONTO/artifact-backend"
    + ` -t ${image}:\${nextRelease.version} -t ${image}:latest .`;

if (!dryRun) {
    publishCmd += ` && docker push --all-tags ${image}`;
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
