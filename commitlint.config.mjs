// Rules for commit messages, checked on pull requests (.github/workflows/commitlint.yml).
// The Conventional Commits preset is the one semantic-release reads versions with.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // bodies quote URLs and logs: their length is not worth a failed check
    'body-max-line-length': [0],
    'footer-max-line-length': [0],
  },
}
