# Working on technocore-receipts

This is an independent, offline companion tool. Keep live participant records,
private keys, signing seeds and local reports outside the repository. Tests may
generate temporary synthetic keys in memory; never persist their private bytes.

The production package must have no network or signing-key access. Do not wire
it into the existing Close Call trading client or change a frozen rules package.

Run `python3 -m unittest discover -s tests -v` after changes. Keep signature
validity separate from server metadata, transcript completeness, settlement and
airdrop eligibility. Publishing, posting and payments need user authorization.
