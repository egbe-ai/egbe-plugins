# Interface implementation and verification

Implement accepted content, behavior and visual direction within their stated scope.
Unspecified routine details can be completed coherently; an omitted choice is not
a prohibition or permission to alter a product promise. Metadata such as plan IDs
or destinations belongs in behavior, not visible copy.

Verify the rendered interface, not only CSS declarations or screenshots:

- Use semantic controls, labels and meaningful errors; keyboard navigation, visible
  focus, dialog focus/return, Esc and accessible close controls must work. Touch
  targets should be comfortably usable (44px is a useful target); never hide a
  necessary control behind a hover-only interaction.
- Check text contrast: at least 4.5:1 for normal text, 3:1 for large text (24px,
  or about 18.7px bold). Keep body text readable; 16px form text avoids iOS input
  zoom. Verify the fonts actually loaded and that fallback layouts remain usable.
- Inspect narrow/mobile and desktop layouts, including tables, long content,
  large numbers and dialogs. Avoid clipping and accidental horizontal page scroll;
  use intentional accessible overflow where content genuinely needs it.
- Respect reduced motion; moving content must not make layout jump or remove the
  usable state. Show progress for pending work and preserve input on recoverable
  failures. Test empty, partial and error states that occur on this path.
- Exercise every distinct changed action and route, including selected-plan and
  return context. A dead destination, fake submit or misleading disabled feature
  is not completed implementation. Do not fabricate proof, screenshots or testimonials.

Use browser inspection and proportionate screenshots to verify the affected path
at realistic widths (for example 375 and 1440px, plus any failing breakpoint).
Computed styles and overflow checks complement visual inspection; neither replaces
the other. Check the project's lint/build and relevant tests. Preserve technical
evidence with the work, excluding credentials and private customer captures from
public output. No fixed palette, image count or report-per-section is required.
