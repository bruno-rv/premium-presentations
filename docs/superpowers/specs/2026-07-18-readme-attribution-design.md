# README attribution design

## Goal

Credit Luan Moreno for inspiration behind some animation and visual design
ideas without implying authorship of the broader Premium Presentations feature
set or implementation.

## Change

Add an **Acknowledgments** section near the end of `README.md` with this text:

> Some animation and visual design ideas were inspired by [Luan Moreno's
> work](https://github.com/luanmorenommaciel). All other features and
> implementation are original to Premium Presentations.

## Constraints

- Keep the attribution concise and limited to inspiration.
- Link to Luan Moreno's GitHub profile using descriptive link text.
- Preserve all existing README content and unrelated workspace changes.
- Do not add the credit to generated decks or runtime assets.

## Verification

- Confirm the new heading and sentence render as valid Markdown.
- Confirm the profile link resolves to Luan Moreno's GitHub profile.
- Run `git diff --check` on the README change.
