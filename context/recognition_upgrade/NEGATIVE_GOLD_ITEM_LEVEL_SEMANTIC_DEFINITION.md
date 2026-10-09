# NEGATIVE_GOLD item-level semantic definition

Status: frozen before audit selection and human review.

## Primary question

> Is an actual human hand visible anywhere in this image?

## Labels

- `NO_HUMAN_HAND_VISIBLE`: no actual human fingertip, finger, partial palm, cropped hand,
  blurred hand, distant hand, lap hand, or edge-visible hand appears anywhere.
- `HUMAN_HAND_VISIBLE`: any recognizable part of a real human hand appears anywhere.
- `UNCERTAIN`: the reviewer genuinely cannot determine whether a region contains an actual
  human hand. This label is never eligible for benchmark selection.

Do not count statues, sculptures, toys, mannequins, drawings, paintings, photographs displayed
inside the scene, cartoons, figurines, or artificial hands as human hands unless an actual human
hand is also visible.

