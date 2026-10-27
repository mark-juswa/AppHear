# Complete combined Text-to-Sign vocabulary inventory

Audit dated 24 October 2026. Read-only application inventory, completed before shoulder repair. Reports may be regenerated after tests; no application code is changed by this script.

Actual branch: `integration/text-to-sign-three-sources-20261023`. The complete 743-entry inventory and 32-motion expansion are preserved in checkpoint `f649e891015cee2e72f0e0d5fc706aa6f7283e3f`. This is the pre-shoulder-repair inventory snapshot; see SHOULDER_REPAIR_REPORT.md for subsequent calibration and test evidence.

The base is `claude/fingerspell-practical-integration` at `1f9e571a8571e78eb06995d6d7f1f2990027608a`; integration is on its separate local branch, not on that remote branch. Working source B is Update 6 at `378213fbd5c948d254cbeb43e344c251138fd91d`; external C is `ff506e8039d0da912d153ad7de46ea2e45bd73cc`. No push or main modification.

The three-source vocabulary union is structurally integrated: 662 entries. Later official 3D-LEX extensions add 49 + 32 = 81, yielding 743. Complete linguistic validation of this union has NOT occurred. The 1,000-entry request remains incomplete.

| Count | Verified value |
|---|---:|
| Original target branch entries | 232 |
| New unique entries from latest working source B | 26 |
| New unique entries from external 647-entry source C | 404 |
| Three-source union | 662 |
| Subsequent official 3D-LEX entries | 81 |
| Current dictionary entries | 743 |
| New dictionary entries vs target branch | 511 |
| Distinct active lexical actions | 742 |
| All packaged actions (includes 26 letters, neutral, 52 inactive alternatives) | 821 |
| Explicit English forms (not unique signs) | 875 |
| Noncanonical alias forms | 132 |
| Alias forms absent from target branch | 77 |
| New aliases attached to target-existing entries | 53 |
| Target-existing entries with changed animation tracks | 36 |
| Registered entries missing named action | 0 |
| Registered entries implemented only through spelling | 0 |
| Qualified linguistic validations | 0 |
| Validated complete phrase translations | 0 |

Unknown A–Z words are automatically fingerspelled. That is an open-ended input space, not a finite additional vocabulary count. ACTION and NICOLE are tested fallback examples. Missing/rejected source candidates are separately listed below; known anatomical defects are not hidden by the zero missing-action count.

## All newly added entries — complete alphabetical table

| Word | Original Source | New or Existing | Animation Source | Playback Status | ASL Validation |
|---|---|---|---|---|---|
| accomplish | External 647-entry package C | New | SIGN_ACCOMPLISH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| act | External 647-entry package C | New | SIGN_ACT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| address | Official 3D-LEX extension after three-source integration | New | SIGN_ADDRESS_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| adult | External 647-entry package C | New | SIGN_ADULT_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| africa | External 647-entry package C | New | SIGN_AFRICA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| against | Official 3D-LEX extension after three-source integration | New | SIGN_AGAINST_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| age | External 647-entry package C | New | SIGN_AGE_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| agreement | External 647-entry package C | New | SIGN_AGREEMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| alcohol | External 647-entry package C | New | SIGN_ALCOHOL_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| alone | Official 3D-LEX extension after three-source integration | New | SIGN_ALONE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| always | Official 3D-LEX extension after three-source integration | New | SIGN_ALWAYS_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| amazing | External 647-entry package C | New | SIGN_AMAZING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| america | External 647-entry package C | New | SIGN_AMERICA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| and | External 647-entry package C | New | SIGN_AND_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| angry | Official 3D-LEX extension after three-source integration | New | SIGN_ANGRY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| answer | External 647-entry package C | New | SIGN_ANSWER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| appear | Official 3D-LEX extension after three-source integration | New | SIGN_APPEAR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| apple | Latest verified working B / Update 6 | New | SIGN_APPLE_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| area | Official 3D-LEX extension after three-source integration | New | SIGN_AREA_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| argue | Official 3D-LEX extension after three-source integration | New | SIGN_ARGUE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| arm | External 647-entry package C | New | SIGN_ARM_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| army | Official 3D-LEX extension after three-source integration | New | SIGN_ARMY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| art | External 647-entry package C | New | SIGN_ART_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| audience | Official 3D-LEX extension after three-source integration | New | SIGN_AUDIENCE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| avoid | Official 3D-LEX extension after three-source integration | New | SIGN_AVOID_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| award | External 647-entry package C | New | SIGN_AWARD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| awkward | External 647-entry package C | New | SIGN_AWKWARD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| back | External 647-entry package C | New | SIGN_BACK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| balance | External 647-entry package C | New | SIGN_BALANCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ball | External 647-entry package C | New | SIGN_BALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| balloon | Official 3D-LEX extension after three-source integration | New | SIGN_BALLOON_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bar | Official 3D-LEX extension after three-source integration | New | SIGN_BAR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| barely | External 647-entry package C | New | SIGN_BARELY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| baseball | External 647-entry package C | New | SIGN_BASEBALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| basement | External 647-entry package C | New | SIGN_BASEMENT_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| basketball | External 647-entry package C | New | SIGN_BASKETBALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bath | Official 3D-LEX extension after three-source integration | New | SIGN_BATH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bathroom | Latest verified working B / Update 6 | New | SIGN_BATHROOM_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| battery | External 647-entry package C | New | SIGN_BATTERY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bear | Official 3D-LEX extension after three-source integration | New | SIGN_BEAR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bedroom | External 647-entry package C | New | SIGN_BEDROOM_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| beg | External 647-entry package C | New | SIGN_BEG_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| behavior | External 647-entry package C | New | SIGN_BEHAVIOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| behind | Official 3D-LEX extension after three-source integration | New | SIGN_BEHIND_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| benefit | External 647-entry package C | New | SIGN_BENEFIT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bet | External 647-entry package C | New | SIGN_BET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bicycle | Official 3D-LEX extension after three-source integration | New | SIGN_BICYCLE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| birth | Official 3D-LEX extension after three-source integration | New | SIGN_BIRTH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| black | External 647-entry package C | New | SIGN_BLACK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| blanket | External 647-entry package C | New | SIGN_BLANKET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bless | External 647-entry package C | New | SIGN_BLESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| blind | External 647-entry package C | New | SIGN_BLIND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bone | External 647-entry package C | New | SIGN_BONE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| boots | External 647-entry package C | New | SIGN_BOOTS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bottle | External 647-entry package C | New | SIGN_BOTTLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bowl | External 647-entry package C | New | SIGN_BOWL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bracelet | External 647-entry package C | New | SIGN_BRACELET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brave | External 647-entry package C | New | SIGN_BRAVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bread | Latest verified working B / Update 6 | New | SIGN_BREAD_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| break | Official 3D-LEX extension after three-source integration | New | SIGN_BREAK_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| breakdown | External 647-entry package C | New | SIGN_BREAKDOWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| breathe | External 647-entry package C | New | SIGN_BREATHE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bridge | External 647-entry package C | New | SIGN_BRIDGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bright | External 647-entry package C | New | SIGN_BRIGHT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brown | External 647-entry package C | New | SIGN_BROWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brush | External 647-entry package C | New | SIGN_BRUSH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bus | External 647-entry package C | New | SIGN_BUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| butterfly | Official 3D-LEX extension after three-source integration | New | SIGN_BUTTERFLY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| cabinet | External 647-entry package C | New | SIGN_CABINET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| california | External 647-entry package C | New | SIGN_CALIFORNIA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| camera | External 647-entry package C | New | SIGN_CAMERA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| can | Latest verified working B / Update 6 | New | SIGN_CAN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| canada | External 647-entry package C | New | SIGN_CANADA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| canoe | External 647-entry package C | New | SIGN_CANOE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| careful | External 647-entry package C | New | SIGN_CAREFUL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cat | External 647-entry package C | New | SIGN_CAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| catholic | External 647-entry package C | New | SIGN_CATHOLIC_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| celebrate | External 647-entry package C | New | SIGN_CELEBRATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| center | External 647-entry package C | New | SIGN_CENTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cereal | External 647-entry package C | New | SIGN_CEREAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| challenge | External 647-entry package C | New | SIGN_CHALLENGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| change | External 647-entry package C | New | SIGN_CHANGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| character | External 647-entry package C | New | SIGN_CHARACTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chase | External 647-entry package C | New | SIGN_CHASE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chat | External 647-entry package C | New | SIGN_CHAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cheap | External 647-entry package C | New | SIGN_CHEAP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cherry | External 647-entry package C | New | SIGN_CHERRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| children | External 647-entry package C | New | SIGN_CHILDREN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chocolate | External 647-entry package C | New | SIGN_CHOCOLATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| choke | External 647-entry package C | New | SIGN_CHOKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| church | Latest verified working B / Update 6 | New | SIGN_CHURCH_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| clear | External 647-entry package C | New | SIGN_CLEAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clock | External 647-entry package C | New | SIGN_CLOCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clown | External 647-entry package C | New | SIGN_CLOWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clueless | External 647-entry package C | New | SIGN_CLUELESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| coffee | Latest verified working B / Update 6 | New | SIGN_COFFEE_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| college | Latest verified working B / Update 6 | New | SIGN_COLLEGE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| comb | External 647-entry package C | New | SIGN_COMB_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| comfortable | External 647-entry package C | New | SIGN_COMFORTABLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| communicate | Latest verified working B / Update 6 | New | SIGN_COMMUNICATE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| complex | Official 3D-LEX extension after three-source integration | New | SIGN_COMPLEX_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| concept | External 647-entry package C | New | SIGN_CONCEPT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| continue | External 647-entry package C | New | SIGN_CONTINUE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cooperate | External 647-entry package C | New | SIGN_COOPERATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| copy | External 647-entry package C | New | SIGN_COPY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cough | External 647-entry package C | New | SIGN_COUGH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| counselor | External 647-entry package C | New | SIGN_COUNSELOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| count | External 647-entry package C | New | SIGN_COUNT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cousin | External 647-entry package C | New | SIGN_COUSIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cow | External 647-entry package C | New | SIGN_COW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cracker | External 647-entry package C | New | SIGN_CRACKER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| crazy | External 647-entry package C | New | SIGN_CRAZY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cry | External 647-entry package C | New | SIGN_CRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cup | External 647-entry package C | New | SIGN_CUP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| curious | External 647-entry package C | New | SIGN_CURIOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dance | External 647-entry package C | New | SIGN_DANCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| danger | Official 3D-LEX extension after three-source integration | New | SIGN_DANGER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| date | External 647-entry package C | New | SIGN_DATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| death | External 647-entry package C | New | SIGN_DEATH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deep | External 647-entry package C | New | SIGN_DEEP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deer | Official 3D-LEX extension after three-source integration | New | SIGN_DEER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| degree | External 647-entry package C | New | SIGN_DEGREE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deny | External 647-entry package C | New | SIGN_DENY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dessert | External 647-entry package C | New | SIGN_DESSERT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| destroy | External 647-entry package C | New | SIGN_DESTROY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| devil | External 647-entry package C | New | SIGN_DEVIL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| diamond | External 647-entry package C | New | SIGN_DIAMOND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| die | External 647-entry package C | New | SIGN_DIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dinosaur | External 647-entry package C | New | SIGN_DINOSAUR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| disappear | External 647-entry package C | New | SIGN_DISAPPEAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| doctor | Latest verified working B / Update 6 | New | SIGN_DOCTOR_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| document | External 647-entry package C | New | SIGN_DOCUMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dog | External 647-entry package C | New | SIGN_DOG_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dormitory | Official 3D-LEX extension after three-source integration | New | SIGN_DORMITORY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| double | External 647-entry package C | New | SIGN_DOUBLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| doubt | External 647-entry package C | New | SIGN_DOUBT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| down | External 647-entry package C | New | SIGN_DOWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dream | Official 3D-LEX extension after three-source integration | New | SIGN_DREAM_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| drug | Official 3D-LEX extension after three-source integration | New | SIGN_DRUG_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| drunk | External 647-entry package C | New | SIGN_DRUNK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dry | Official 3D-LEX extension after three-source integration | New | SIGN_DRY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| duck | External 647-entry package C | New | SIGN_DUCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dye | External 647-entry package C | New | SIGN_DYE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| eagle | External 647-entry package C | New | SIGN_EAGLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ear | External 647-entry package C | New | SIGN_EAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| earn | External 647-entry package C | New | SIGN_EARN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| earth | External 647-entry package C | New | SIGN_EARTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| earthquake | External 647-entry package C | New | SIGN_EARTHQUAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| egypt | External 647-entry package C | New | SIGN_EGYPT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| electrician | External 647-entry package C | New | SIGN_ELECTRICIAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| elephant | External 647-entry package C | New | SIGN_ELEPHANT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| email | External 647-entry package C | New | SIGN_EMAIL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| embarrass | External 647-entry package C | New | SIGN_EMBARRASS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| end | Official 3D-LEX extension after three-source integration | New | SIGN_END_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| enough | External 647-entry package C | New | SIGN_ENOUGH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| enter | Official 3D-LEX extension after three-source integration | New | SIGN_ENTER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| equal | External 647-entry package C | New | SIGN_EQUAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| europe | External 647-entry package C | New | SIGN_EUROPE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| event | External 647-entry package C | New | SIGN_EVENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| everyday | External 647-entry package C | New | SIGN_EVERYDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| evidence | External 647-entry package C | New | SIGN_EVIDENCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| expect | Official 3D-LEX extension after three-source integration | New | SIGN_EXPECT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| expensive | External 647-entry package C | New | SIGN_EXPENSIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| experiment | External 647-entry package C | New | SIGN_EXPERIMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| expert | Official 3D-LEX extension after three-source integration | New | SIGN_EXPERT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| explain | Latest verified working B / Update 6 | New | SIGN_EXPLAIN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| eyeglasses | External 647-entry package C | New | SIGN_EYEGLASSES_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fail | External 647-entry package C | New | SIGN_FAIL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fake | External 647-entry package C | New | SIGN_FAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| famous | External 647-entry package C | New | SIGN_FAMOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| far | External 647-entry package C | New | SIGN_FAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fight | Official 3D-LEX extension after three-source integration | New | SIGN_FIGHT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| finally | External 647-entry package C | New | SIGN_FINALLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fine | Latest verified working B / Update 6 | New | SIGN_FINE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fire | External 647-entry package C | New | SIGN_FIRE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fish | Official 3D-LEX extension after three-source integration | New | SIGN_FISH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| floor | External 647-entry package C | New | SIGN_FLOOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| flower | External 647-entry package C | New | SIGN_FLOWER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| flute | External 647-entry package C | New | SIGN_FLUTE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fly | External 647-entry package C | New | SIGN_FLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| forbid | External 647-entry package C | New | SIGN_FORBID_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| forest | Official 3D-LEX extension after three-source integration | New | SIGN_FOREST_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| form | External 647-entry package C | New | SIGN_FORM_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| former | External 647-entry package C | New | SIGN_FORMER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| four | External 647-entry package C | New | SIGN_FOUR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| french | External 647-entry package C | New | SIGN_FRENCH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| friday | External 647-entry package C | New | SIGN_FRIDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| friendly | Official 3D-LEX extension after three-source integration | New | SIGN_FRIENDLY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| fruit | External 647-entry package C | New | SIGN_FRUIT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| full | Official 3D-LEX extension after three-source integration | New | SIGN_FULL_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| funny | External 647-entry package C | New | SIGN_FUNNY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| furniture | External 647-entry package C | New | SIGN_FURNITURE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| future | External 647-entry package C | New | SIGN_FUTURE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gamble | Official 3D-LEX extension after three-source integration | New | SIGN_GAMBLE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| gas | External 647-entry package C | New | SIGN_GAS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gay | External 647-entry package C | New | SIGN_GAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| generation | External 647-entry package C | New | SIGN_GENERATION_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ghost | External 647-entry package C | New | SIGN_GHOST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| girl | External 647-entry package C | New | SIGN_GIRL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gloves | Official 3D-LEX extension after three-source integration | New | SIGN_GLOVES_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| goal | External 647-entry package C | New | SIGN_GOAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| goat | External 647-entry package C | New | SIGN_GOAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gone | External 647-entry package C | New | SIGN_GONE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gossip | External 647-entry package C | New | SIGN_GOSSIP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| government | External 647-entry package C | New | SIGN_GOVERNMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grapes | External 647-entry package C | New | SIGN_GRAPES_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grass | External 647-entry package C | New | SIGN_GRASS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gray | External 647-entry package C | New | SIGN_GRAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| green | External 647-entry package C | New | SIGN_GREEN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grow | External 647-entry package C | New | SIGN_GROW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hair | External 647-entry package C | New | SIGN_HAIR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| haircut | External 647-entry package C | New | SIGN_HAIRCUT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hanukkah | External 647-entry package C | New | SIGN_HANUKKAH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| happen | Official 3D-LEX extension after three-source integration | New | SIGN_HAPPEN_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| hat | External 647-entry package C | New | SIGN_HAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hawaii | External 647-entry package C | New | SIGN_HAWAII_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| head | External 647-entry package C | New | SIGN_HEAD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| headache | External 647-entry package C | New | SIGN_HEADACHE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| health | External 647-entry package C | New | SIGN_HEALTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| heaven | External 647-entry package C | New | SIGN_HEAVEN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| heavy | External 647-entry package C | New | SIGN_HEAVY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| helmet | External 647-entry package C | New | SIGN_HELMET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hide | Official 3D-LEX extension after three-source integration | New | SIGN_HIDE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| history | External 647-entry package C | New | SIGN_HISTORY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hockey | External 647-entry package C | New | SIGN_HOCKEY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| homework | External 647-entry package C | New | SIGN_HOMEWORK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| honest | External 647-entry package C | New | SIGN_HONEST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| honor | External 647-entry package C | New | SIGN_HONOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hope | External 647-entry package C | New | SIGN_HOPE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| horse | External 647-entry package C | New | SIGN_HORSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hotel | Latest verified working B / Update 6 | New | SIGN_HOTEL_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| hunt | External 647-entry package C | New | SIGN_HUNT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hurricane | External 647-entry package C | New | SIGN_HURRICANE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hurry | External 647-entry package C | New | SIGN_HURRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hurt | Official 3D-LEX extension after three-source integration | New | SIGN_HURT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| idea | External 647-entry package C | New | SIGN_IDEA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| impact | External 647-entry package C | New | SIGN_IMPACT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| impossible | External 647-entry package C | New | SIGN_IMPOSSIBLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| improve | Official 3D-LEX extension after three-source integration | New | SIGN_IMPROVE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| innocent | External 647-entry package C | New | SIGN_INNOCENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| inside | External 647-entry package C | New | SIGN_INSIDE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| insurance | External 647-entry package C | New | SIGN_INSURANCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| internet | External 647-entry package C | New | SIGN_INTERNET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| introduce | External 647-entry package C | New | SIGN_INTRODUCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| invite | External 647-entry package C | New | SIGN_INVITE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| iron | Official 3D-LEX extension after three-source integration | New | SIGN_IRON_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| italy | External 647-entry package C | New | SIGN_ITALY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| japan | External 647-entry package C | New | SIGN_JAPAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| jealous | External 647-entry package C | New | SIGN_JEALOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| jewish | External 647-entry package C | New | SIGN_JEWISH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| join | External 647-entry package C | New | SIGN_JOIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| joke | External 647-entry package C | New | SIGN_JOKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| journey | External 647-entry package C | New | SIGN_JOURNEY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| jump | External 647-entry package C | New | SIGN_JUMP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| keyboard | External 647-entry package C | New | SIGN_KEYBOARD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| kitchen | Latest verified working B / Update 6 | New | SIGN_KITCHEN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| knife | Official 3D-LEX extension after three-source integration | New | SIGN_KNIFE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| label | External 647-entry package C | New | SIGN_LABEL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lamp | External 647-entry package C | New | SIGN_LAMP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| laptop | Official 3D-LEX extension after three-source integration | New | SIGN_LAPTOP_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| late | Official 3D-LEX extension after three-source integration | New | SIGN_LATE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| law | External 647-entry package C | New | SIGN_LAW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lawyer | External 647-entry package C | New | SIGN_LAWYER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lazy | External 647-entry package C | New | SIGN_LAZY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| leak | External 647-entry package C | New | SIGN_LEAK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lecture | Official 3D-LEX extension after three-source integration | New | SIGN_LECTURE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| less | External 647-entry package C | New | SIGN_LESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lettuce | External 647-entry package C | New | SIGN_LETTUCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| library | Latest verified working B / Update 6 | New | SIGN_LIBRARY_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| license | External 647-entry package C | New | SIGN_LICENSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lie | External 647-entry package C | New | SIGN_LIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lipstick | External 647-entry package C | New | SIGN_LIPSTICK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lobster | External 647-entry package C | New | SIGN_LOBSTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lock | External 647-entry package C | New | SIGN_LOCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lonely | External 647-entry package C | New | SIGN_LONELY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| long | Official 3D-LEX extension after three-source integration | New | SIGN_LONG_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| lousy | External 647-entry package C | New | SIGN_LOUSY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lucky | External 647-entry package C | New | SIGN_LUCKY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mad | Official 3D-LEX extension after three-source integration | New | SIGN_MAD_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| magazine | External 647-entry package C | New | SIGN_MAGAZINE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| marry | External 647-entry package C | New | SIGN_MARRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| math | External 647-entry package C | New | SIGN_MATH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| maybe | External 647-entry package C | New | SIGN_MAYBE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| meeting | External 647-entry package C | New | SIGN_MEETING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| member | External 647-entry package C | New | SIGN_MEMBER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| memorize | External 647-entry package C | New | SIGN_MEMORIZE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| microwave | External 647-entry package C | New | SIGN_MICROWAVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| milk | Latest verified working B / Update 6 | New | SIGN_MILK_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mirror | Official 3D-LEX extension after three-source integration | New | SIGN_MIRROR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| misunderstand | External 647-entry package C | New | SIGN_MISUNDERSTAND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mock | External 647-entry package C | New | SIGN_MOCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| monkey | External 647-entry package C | New | SIGN_MONKEY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| monster | External 647-entry package C | New | SIGN_MONSTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| moon | External 647-entry package C | New | SIGN_MOON_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mouse | Official 3D-LEX extension after three-source integration | New | SIGN_MOUSE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| mouth | Official 3D-LEX extension after three-source integration | New | SIGN_MOUTH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| movie | External 647-entry package C | New | SIGN_MOVIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| music | External 647-entry package C | New | SIGN_MUSIC_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| napkin | External 647-entry package C | New | SIGN_NAPKIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| necklace | Official 3D-LEX extension after three-source integration | New | SIGN_NECKLACE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| negative | External 647-entry package C | New | SIGN_NEGATIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| nephew | External 647-entry package C | New | SIGN_NEPHEW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| never | External 647-entry package C | New | SIGN_NEVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| newspaper | External 647-entry package C | New | SIGN_NEWSPAPER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| next | Official 3D-LEX extension after three-source integration | New | SIGN_NEXT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| nice | Latest verified working B / Update 6 | New | SIGN_NICE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| niece | External 647-entry package C | New | SIGN_NIECE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| normal | External 647-entry package C | New | SIGN_NORMAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| north | External 647-entry package C | New | SIGN_NORTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| nose | Official 3D-LEX extension after three-source integration | New | SIGN_NOSE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| not | Latest verified working B / Update 6 | New | SIGN_NOT_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| nurse | Latest verified working B / Update 6 | New | SIGN_NURSE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| obsess | External 647-entry package C | New | SIGN_OBSESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ocean | Official 3D-LEX extension after three-source integration | New | SIGN_OCEAN_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| off | External 647-entry package C | New | SIGN_OFF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| on | External 647-entry package C | New | SIGN_ON_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| orange | Latest verified working B / Update 6 | New | SIGN_ORANGE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| other | External 647-entry package C | New | SIGN_OTHER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| outside | External 647-entry package C | New | SIGN_OUTSIDE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| over | External 647-entry package C | New | SIGN_OVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| overlook | External 647-entry package C | New | SIGN_OVERLOOK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| owl | External 647-entry package C | New | SIGN_OWL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pack | External 647-entry package C | New | SIGN_PACK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pain | Latest verified working B / Update 6 | New | SIGN_PAIN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| paint | External 647-entry package C | New | SIGN_PAINT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| parade | External 647-entry package C | New | SIGN_PARADE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pass | External 647-entry package C | New | SIGN_PASS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| past | Official 3D-LEX extension after three-source integration | New | SIGN_PAST_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| pepper | External 647-entry package C | New | SIGN_PEPPER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| perfect | External 647-entry package C | New | SIGN_PERFECT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| perspective | External 647-entry package C | New | SIGN_PERSPECTIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| piano | External 647-entry package C | New | SIGN_PIANO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| picture | External 647-entry package C | New | SIGN_PICTURE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pie | External 647-entry package C | New | SIGN_PIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pink | External 647-entry package C | New | SIGN_PINK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pity | External 647-entry package C | New | SIGN_PITY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| place | External 647-entry package C | New | SIGN_PLACE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plan | External 647-entry package C | New | SIGN_PLAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plant | External 647-entry package C | New | SIGN_PLANT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plate | External 647-entry package C | New | SIGN_PLATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plenty | External 647-entry package C | New | SIGN_PLENTY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plus | External 647-entry package C | New | SIGN_PLUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| point | External 647-entry package C | New | SIGN_POINT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| poop | External 647-entry package C | New | SIGN_POOP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| popular | External 647-entry package C | New | SIGN_POPULAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| postpone | External 647-entry package C | New | SIGN_POSTPONE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| potato | External 647-entry package C | New | SIGN_POTATO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| power | External 647-entry package C | New | SIGN_POWER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| precious | External 647-entry package C | New | SIGN_PRECIOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| president | External 647-entry package C | New | SIGN_PRESIDENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| price | External 647-entry package C | New | SIGN_PRICE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pride | Official 3D-LEX extension after three-source integration | New | SIGN_PRIDE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| print | External 647-entry package C | New | SIGN_PRINT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| promote | External 647-entry package C | New | SIGN_PROMOTE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pull | External 647-entry package C | New | SIGN_PULL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| punish | Official 3D-LEX extension after three-source integration | New | SIGN_PUNISH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| purple | External 647-entry package C | New | SIGN_PURPLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| push | External 647-entry package C | New | SIGN_PUSH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| put | External 647-entry package C | New | SIGN_PUT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| puzzled | Official 3D-LEX extension after three-source integration | New | SIGN_PUZZLED_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| queen | External 647-entry package C | New | SIGN_QUEEN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| quiet | External 647-entry package C | New | SIGN_QUIET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| race | External 647-entry package C | New | SIGN_RACE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rake | External 647-entry package C | New | SIGN_RAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| really | External 647-entry package C | New | SIGN_REALLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| red | External 647-entry package C | New | SIGN_RED_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| refuse | External 647-entry package C | New | SIGN_REFUSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| relationship | External 647-entry package C | New | SIGN_RELATIONSHIP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| relax | Official 3D-LEX extension after three-source integration | New | SIGN_RELAX_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| request | External 647-entry package C | New | SIGN_REQUEST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| research | External 647-entry package C | New | SIGN_RESEARCH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| responsibility | External 647-entry package C | New | SIGN_RESPONSIBILITY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| result | External 647-entry package C | New | SIGN_RESULT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rich | Official 3D-LEX extension after three-source integration | New | SIGN_RICH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| rob | External 647-entry package C | New | SIGN_ROB_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rock | External 647-entry package C | New | SIGN_ROCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rude | External 647-entry package C | New | SIGN_RUDE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ruin | External 647-entry package C | New | SIGN_RUIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| salad | External 647-entry package C | New | SIGN_SALAD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sandwich | External 647-entry package C | New | SIGN_SANDWICH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| scared | External 647-entry package C | New | SIGN_SCARED_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| schedule | External 647-entry package C | New | SIGN_SCHEDULE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| scold | External 647-entry package C | New | SIGN_SCOLD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| scream | External 647-entry package C | New | SIGN_SCREAM_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| screwdriver | External 647-entry package C | New | SIGN_SCREWDRIVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| secretary | External 647-entry package C | New | SIGN_SECRETARY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sensitive | External 647-entry package C | New | SIGN_SENSITIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sentence | External 647-entry package C | New | SIGN_SENTENCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| serious | External 647-entry package C | New | SIGN_SERIOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sew | External 647-entry package C | New | SIGN_SEW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| share | Official 3D-LEX extension after three-source integration | New | SIGN_SHARE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| sheep | External 647-entry package C | New | SIGN_SHEEP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shelf | External 647-entry package C | New | SIGN_SHELF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shirt | External 647-entry package C | New | SIGN_SHIRT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shovel | External 647-entry package C | New | SIGN_SHOVEL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| show | External 647-entry package C | New | SIGN_SHOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sign | Latest verified working B / Update 6 | New | SIGN_SIGN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| silly | External 647-entry package C | New | SIGN_SILLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| since | External 647-entry package C | New | SIGN_SINCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sing | Official 3D-LEX extension after three-source integration | New | SIGN_SING_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| skill | External 647-entry package C | New | SIGN_SKILL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| skin | External 647-entry package C | New | SIGN_SKIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| smart | External 647-entry package C | New | SIGN_SMART_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| smell | Official 3D-LEX extension after three-source integration | New | SIGN_SMELL_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| smile | External 647-entry package C | New | SIGN_SMILE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| smooth | External 647-entry package C | New | SIGN_SMOOTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| snake | External 647-entry package C | New | SIGN_SNAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| snow | External 647-entry package C | New | SIGN_SNOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| soap | Official 3D-LEX extension after three-source integration | New | SIGN_SOAP_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| soccer | External 647-entry package C | New | SIGN_SOCCER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sofa | External 647-entry package C | New | SIGN_SOFA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| soft | External 647-entry package C | New | SIGN_SOFT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sound | External 647-entry package C | New | SIGN_SOUND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| soup | External 647-entry package C | New | SIGN_SOUP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sour | Official 3D-LEX extension after three-source integration | New | SIGN_SOUR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| spider | External 647-entry package C | New | SIGN_SPIDER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| spoon | External 647-entry package C | New | SIGN_SPOON_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| spring | External 647-entry package C | New | SIGN_SPRING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| square | External 647-entry package C | New | SIGN_SQUARE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| squirrel | External 647-entry package C | New | SIGN_SQUIRREL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| staff | External 647-entry package C | New | SIGN_STAFF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stairs | External 647-entry package C | New | SIGN_STAIRS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stamp | External 647-entry package C | New | SIGN_STAMP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stare | External 647-entry package C | New | SIGN_STARE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| steal | External 647-entry package C | New | SIGN_STEAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sting | External 647-entry package C | New | SIGN_STING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stir | External 647-entry package C | New | SIGN_STIR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| straight | External 647-entry package C | New | SIGN_STRAIGHT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| strange | External 647-entry package C | New | SIGN_STRANGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stress | External 647-entry package C | New | SIGN_STRESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| struggle | External 647-entry package C | New | SIGN_STRUGGLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stubborn | Official 3D-LEX extension after three-source integration | New | SIGN_STUBBORN_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| stuck | External 647-entry package C | New | SIGN_STUCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| study | Latest verified working B / Update 6 | New | SIGN_STUDY_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| summer | Official 3D-LEX extension after three-source integration | New | SIGN_SUMMER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| sunrise | External 647-entry package C | New | SIGN_SUNRISE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| surgery | External 647-entry package C | New | SIGN_SURGERY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| surprise | External 647-entry package C | New | SIGN_SURPRISE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| suspect | Official 3D-LEX extension after three-source integration | New | SIGN_SUSPECT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| swallow | External 647-entry package C | New | SIGN_SWALLOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sweet | External 647-entry package C | New | SIGN_SWEET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sweetheart | Official 3D-LEX extension after three-source integration | New | SIGN_SWEETHEART_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| swing | External 647-entry package C | New | SIGN_SWING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tan | External 647-entry package C | New | SIGN_TAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tea | Latest verified working B / Update 6 | New | SIGN_TEA_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tennis | External 647-entry package C | New | SIGN_TENNIS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| test | External 647-entry package C | New | SIGN_TEST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| text | Official 3D-LEX extension after three-source integration | New | SIGN_TEXT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| therapy | External 647-entry package C | New | SIGN_THERAPY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thermometer | External 647-entry package C | New | SIGN_THERMOMETER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thin | External 647-entry package C | New | SIGN_THIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thirsty | External 647-entry package C | New | SIGN_THIRSTY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| three | External 647-entry package C | New | SIGN_THREE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| throw | External 647-entry package C | New | SIGN_THROW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thursday | External 647-entry package C | New | SIGN_THURSDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tiger | Official 3D-LEX extension after three-source integration | New | SIGN_TIGER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| tissue | External 647-entry package C | New | SIGN_TISSUE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tobacco | External 647-entry package C | New | SIGN_TOBACCO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| together | Latest verified working B / Update 6 | New | SIGN_TOGETHER_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| toilet | External 647-entry package C | New | SIGN_TOILET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tomato | External 647-entry package C | New | SIGN_TOMATO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| top | External 647-entry package C | New | SIGN_TOP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tornado | External 647-entry package C | New | SIGN_TORNADO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| touch | External 647-entry package C | New | SIGN_TOUCH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tournament | External 647-entry package C | New | SIGN_TOURNAMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| towel | External 647-entry package C | New | SIGN_TOWEL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| traffic | Official 3D-LEX extension after three-source integration | New | SIGN_TRAFFIC_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| train | External 647-entry package C | New | SIGN_TRAIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| transfer | External 647-entry package C | New | SIGN_TRANSFER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| trouble | External 647-entry package C | New | SIGN_TROUBLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| truth | External 647-entry package C | New | SIGN_TRUTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| turtle | External 647-entry package C | New | SIGN_TURTLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| two | External 647-entry package C | New | SIGN_TWO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ugly | External 647-entry package C | New | SIGN_UGLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| uncle | External 647-entry package C | New | SIGN_UNCLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| under | Official 3D-LEX extension after three-source integration | New | SIGN_UNDER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| unique | External 647-entry package C | New | SIGN_UNIQUE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| university | Latest verified working B / Update 6 | New | SIGN_UNIVERSITY_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| up | Official 3D-LEX extension after three-source integration | New | SIGN_UP_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| vampire | External 647-entry package C | New | SIGN_VAMPIRE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| verb | External 647-entry package C | New | SIGN_VERB_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| violin | External 647-entry package C | New | SIGN_VIOLIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| visualize | External 647-entry package C | New | SIGN_VISUALIZE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| voice | External 647-entry package C | New | SIGN_VOICE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| volunteer | External 647-entry package C | New | SIGN_VOLUNTEER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| vote | External 647-entry package C | New | SIGN_VOTE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| waiter | External 647-entry package C | New | SIGN_WAITER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wall | External 647-entry package C | New | SIGN_WALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wander | External 647-entry package C | New | SIGN_WANDER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| warn | External 647-entry package C | New | SIGN_WARN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| way | Official 3D-LEX extension after three-source integration | New | SIGN_WAY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| we | Official 3D-LEX extension after three-source integration | New | SIGN_WE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| weak | External 647-entry package C | New | SIGN_WEAK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| weather | External 647-entry package C | New | SIGN_WEATHER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wednesday | External 647-entry package C | New | SIGN_WEDNESDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| weight | External 647-entry package C | New | SIGN_WEIGHT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wet | External 647-entry package C | New | SIGN_WET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| whatever | External 647-entry package C | New | SIGN_WHATEVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| will | External 647-entry package C | New | SIGN_WILL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wind | External 647-entry package C | New | SIGN_WIND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wine | External 647-entry package C | New | SIGN_WINE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| with | Latest verified working B / Update 6 | New | SIGN_WITH_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wolf | External 647-entry package C | New | SIGN_WOLF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wonder | Official 3D-LEX extension after three-source integration | New | SIGN_WONDER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| wood | Official 3D-LEX extension after three-source integration | New | SIGN_WOOD_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| worry | External 647-entry package C | New | SIGN_WORRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| worse | External 647-entry package C | New | SIGN_WORSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wow | Official 3D-LEX extension after three-source integration | New | SIGN_WOW_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| yellow | External 647-entry package C | New | SIGN_YELLOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| young | External 647-entry package C | New | SIGN_YOUNG_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| zero | External 647-entry package C | New | SIGN_ZERO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |

## Contribution from latest working source B — complete list

| Word | Original Source | New or Existing | Animation Source | Playback Status | ASL Validation |
|---|---|---|---|---|---|
| apple | Latest verified working B / Update 6 | New | SIGN_APPLE_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| bathroom | Latest verified working B / Update 6 | New | SIGN_BATHROOM_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bread | Latest verified working B / Update 6 | New | SIGN_BREAD_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| can | Latest verified working B / Update 6 | New | SIGN_CAN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| church | Latest verified working B / Update 6 | New | SIGN_CHURCH_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| coffee | Latest verified working B / Update 6 | New | SIGN_COFFEE_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| college | Latest verified working B / Update 6 | New | SIGN_COLLEGE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| communicate | Latest verified working B / Update 6 | New | SIGN_COMMUNICATE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| doctor | Latest verified working B / Update 6 | New | SIGN_DOCTOR_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| explain | Latest verified working B / Update 6 | New | SIGN_EXPLAIN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fine | Latest verified working B / Update 6 | New | SIGN_FINE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hotel | Latest verified working B / Update 6 | New | SIGN_HOTEL_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| kitchen | Latest verified working B / Update 6 | New | SIGN_KITCHEN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| library | Latest verified working B / Update 6 | New | SIGN_LIBRARY_HUMAN_AUTHORED_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| milk | Latest verified working B / Update 6 | New | SIGN_MILK_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| nice | Latest verified working B / Update 6 | New | SIGN_NICE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| not | Latest verified working B / Update 6 | New | SIGN_NOT_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| nurse | Latest verified working B / Update 6 | New | SIGN_NURSE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| orange | Latest verified working B / Update 6 | New | SIGN_ORANGE_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pain | Latest verified working B / Update 6 | New | SIGN_PAIN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sign | Latest verified working B / Update 6 | New | SIGN_SIGN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| study | Latest verified working B / Update 6 | New | SIGN_STUDY_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tea | Latest verified working B / Update 6 | New | SIGN_TEA_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| together | Latest verified working B / Update 6 | New | SIGN_TOGETHER_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| university | Latest verified working B / Update 6 | New | SIGN_UNIVERSITY_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| with | Latest verified working B / Update 6 | New | SIGN_WITH_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |

## Contribution from external 647-entry package C — complete list

| Word | Original Source | New or Existing | Animation Source | Playback Status | ASL Validation |
|---|---|---|---|---|---|
| accomplish | External 647-entry package C | New | SIGN_ACCOMPLISH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| act | External 647-entry package C | New | SIGN_ACT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| adult | External 647-entry package C | New | SIGN_ADULT_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| africa | External 647-entry package C | New | SIGN_AFRICA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| age | External 647-entry package C | New | SIGN_AGE_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| agreement | External 647-entry package C | New | SIGN_AGREEMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| alcohol | External 647-entry package C | New | SIGN_ALCOHOL_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| amazing | External 647-entry package C | New | SIGN_AMAZING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| america | External 647-entry package C | New | SIGN_AMERICA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| and | External 647-entry package C | New | SIGN_AND_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| answer | External 647-entry package C | New | SIGN_ANSWER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| arm | External 647-entry package C | New | SIGN_ARM_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| art | External 647-entry package C | New | SIGN_ART_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| award | External 647-entry package C | New | SIGN_AWARD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| awkward | External 647-entry package C | New | SIGN_AWKWARD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| back | External 647-entry package C | New | SIGN_BACK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| balance | External 647-entry package C | New | SIGN_BALANCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ball | External 647-entry package C | New | SIGN_BALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| barely | External 647-entry package C | New | SIGN_BARELY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| baseball | External 647-entry package C | New | SIGN_BASEBALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| basement | External 647-entry package C | New | SIGN_BASEMENT_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| basketball | External 647-entry package C | New | SIGN_BASKETBALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| battery | External 647-entry package C | New | SIGN_BATTERY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bedroom | External 647-entry package C | New | SIGN_BEDROOM_3DLEX_ASL_PREVIEW | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| beg | External 647-entry package C | New | SIGN_BEG_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| behavior | External 647-entry package C | New | SIGN_BEHAVIOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| benefit | External 647-entry package C | New | SIGN_BENEFIT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bet | External 647-entry package C | New | SIGN_BET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| black | External 647-entry package C | New | SIGN_BLACK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| blanket | External 647-entry package C | New | SIGN_BLANKET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bless | External 647-entry package C | New | SIGN_BLESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| blind | External 647-entry package C | New | SIGN_BLIND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bone | External 647-entry package C | New | SIGN_BONE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| boots | External 647-entry package C | New | SIGN_BOOTS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bottle | External 647-entry package C | New | SIGN_BOTTLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bowl | External 647-entry package C | New | SIGN_BOWL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bracelet | External 647-entry package C | New | SIGN_BRACELET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brave | External 647-entry package C | New | SIGN_BRAVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| breakdown | External 647-entry package C | New | SIGN_BREAKDOWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| breathe | External 647-entry package C | New | SIGN_BREATHE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bridge | External 647-entry package C | New | SIGN_BRIDGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bright | External 647-entry package C | New | SIGN_BRIGHT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brown | External 647-entry package C | New | SIGN_BROWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brush | External 647-entry package C | New | SIGN_BRUSH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bus | External 647-entry package C | New | SIGN_BUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cabinet | External 647-entry package C | New | SIGN_CABINET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| california | External 647-entry package C | New | SIGN_CALIFORNIA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| camera | External 647-entry package C | New | SIGN_CAMERA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| canada | External 647-entry package C | New | SIGN_CANADA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| canoe | External 647-entry package C | New | SIGN_CANOE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| careful | External 647-entry package C | New | SIGN_CAREFUL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cat | External 647-entry package C | New | SIGN_CAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| catholic | External 647-entry package C | New | SIGN_CATHOLIC_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| celebrate | External 647-entry package C | New | SIGN_CELEBRATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| center | External 647-entry package C | New | SIGN_CENTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cereal | External 647-entry package C | New | SIGN_CEREAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| challenge | External 647-entry package C | New | SIGN_CHALLENGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| change | External 647-entry package C | New | SIGN_CHANGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| character | External 647-entry package C | New | SIGN_CHARACTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chase | External 647-entry package C | New | SIGN_CHASE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chat | External 647-entry package C | New | SIGN_CHAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cheap | External 647-entry package C | New | SIGN_CHEAP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cherry | External 647-entry package C | New | SIGN_CHERRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| children | External 647-entry package C | New | SIGN_CHILDREN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chocolate | External 647-entry package C | New | SIGN_CHOCOLATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| choke | External 647-entry package C | New | SIGN_CHOKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clear | External 647-entry package C | New | SIGN_CLEAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clock | External 647-entry package C | New | SIGN_CLOCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clown | External 647-entry package C | New | SIGN_CLOWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clueless | External 647-entry package C | New | SIGN_CLUELESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| comb | External 647-entry package C | New | SIGN_COMB_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| comfortable | External 647-entry package C | New | SIGN_COMFORTABLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| concept | External 647-entry package C | New | SIGN_CONCEPT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| continue | External 647-entry package C | New | SIGN_CONTINUE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cooperate | External 647-entry package C | New | SIGN_COOPERATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| copy | External 647-entry package C | New | SIGN_COPY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cough | External 647-entry package C | New | SIGN_COUGH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| counselor | External 647-entry package C | New | SIGN_COUNSELOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| count | External 647-entry package C | New | SIGN_COUNT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cousin | External 647-entry package C | New | SIGN_COUSIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cow | External 647-entry package C | New | SIGN_COW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cracker | External 647-entry package C | New | SIGN_CRACKER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| crazy | External 647-entry package C | New | SIGN_CRAZY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cry | External 647-entry package C | New | SIGN_CRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cup | External 647-entry package C | New | SIGN_CUP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| curious | External 647-entry package C | New | SIGN_CURIOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dance | External 647-entry package C | New | SIGN_DANCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| date | External 647-entry package C | New | SIGN_DATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| death | External 647-entry package C | New | SIGN_DEATH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deep | External 647-entry package C | New | SIGN_DEEP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| degree | External 647-entry package C | New | SIGN_DEGREE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deny | External 647-entry package C | New | SIGN_DENY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dessert | External 647-entry package C | New | SIGN_DESSERT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| destroy | External 647-entry package C | New | SIGN_DESTROY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| devil | External 647-entry package C | New | SIGN_DEVIL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| diamond | External 647-entry package C | New | SIGN_DIAMOND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| die | External 647-entry package C | New | SIGN_DIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dinosaur | External 647-entry package C | New | SIGN_DINOSAUR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| disappear | External 647-entry package C | New | SIGN_DISAPPEAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| document | External 647-entry package C | New | SIGN_DOCUMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dog | External 647-entry package C | New | SIGN_DOG_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| double | External 647-entry package C | New | SIGN_DOUBLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| doubt | External 647-entry package C | New | SIGN_DOUBT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| down | External 647-entry package C | New | SIGN_DOWN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| drunk | External 647-entry package C | New | SIGN_DRUNK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| duck | External 647-entry package C | New | SIGN_DUCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| dye | External 647-entry package C | New | SIGN_DYE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| eagle | External 647-entry package C | New | SIGN_EAGLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ear | External 647-entry package C | New | SIGN_EAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| earn | External 647-entry package C | New | SIGN_EARN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| earth | External 647-entry package C | New | SIGN_EARTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| earthquake | External 647-entry package C | New | SIGN_EARTHQUAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| egypt | External 647-entry package C | New | SIGN_EGYPT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| electrician | External 647-entry package C | New | SIGN_ELECTRICIAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| elephant | External 647-entry package C | New | SIGN_ELEPHANT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| email | External 647-entry package C | New | SIGN_EMAIL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| embarrass | External 647-entry package C | New | SIGN_EMBARRASS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| enough | External 647-entry package C | New | SIGN_ENOUGH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| equal | External 647-entry package C | New | SIGN_EQUAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| europe | External 647-entry package C | New | SIGN_EUROPE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| event | External 647-entry package C | New | SIGN_EVENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| everyday | External 647-entry package C | New | SIGN_EVERYDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| evidence | External 647-entry package C | New | SIGN_EVIDENCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| expensive | External 647-entry package C | New | SIGN_EXPENSIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| experiment | External 647-entry package C | New | SIGN_EXPERIMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| eyeglasses | External 647-entry package C | New | SIGN_EYEGLASSES_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fail | External 647-entry package C | New | SIGN_FAIL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fake | External 647-entry package C | New | SIGN_FAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| famous | External 647-entry package C | New | SIGN_FAMOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| far | External 647-entry package C | New | SIGN_FAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| finally | External 647-entry package C | New | SIGN_FINALLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fire | External 647-entry package C | New | SIGN_FIRE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| floor | External 647-entry package C | New | SIGN_FLOOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| flower | External 647-entry package C | New | SIGN_FLOWER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| flute | External 647-entry package C | New | SIGN_FLUTE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fly | External 647-entry package C | New | SIGN_FLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| forbid | External 647-entry package C | New | SIGN_FORBID_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| form | External 647-entry package C | New | SIGN_FORM_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| former | External 647-entry package C | New | SIGN_FORMER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| four | External 647-entry package C | New | SIGN_FOUR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| french | External 647-entry package C | New | SIGN_FRENCH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| friday | External 647-entry package C | New | SIGN_FRIDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fruit | External 647-entry package C | New | SIGN_FRUIT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| funny | External 647-entry package C | New | SIGN_FUNNY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| furniture | External 647-entry package C | New | SIGN_FURNITURE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| future | External 647-entry package C | New | SIGN_FUTURE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gas | External 647-entry package C | New | SIGN_GAS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gay | External 647-entry package C | New | SIGN_GAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| generation | External 647-entry package C | New | SIGN_GENERATION_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ghost | External 647-entry package C | New | SIGN_GHOST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| girl | External 647-entry package C | New | SIGN_GIRL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| goal | External 647-entry package C | New | SIGN_GOAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| goat | External 647-entry package C | New | SIGN_GOAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gone | External 647-entry package C | New | SIGN_GONE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gossip | External 647-entry package C | New | SIGN_GOSSIP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| government | External 647-entry package C | New | SIGN_GOVERNMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grapes | External 647-entry package C | New | SIGN_GRAPES_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grass | External 647-entry package C | New | SIGN_GRASS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| gray | External 647-entry package C | New | SIGN_GRAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| green | External 647-entry package C | New | SIGN_GREEN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grow | External 647-entry package C | New | SIGN_GROW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hair | External 647-entry package C | New | SIGN_HAIR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| haircut | External 647-entry package C | New | SIGN_HAIRCUT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hanukkah | External 647-entry package C | New | SIGN_HANUKKAH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hat | External 647-entry package C | New | SIGN_HAT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hawaii | External 647-entry package C | New | SIGN_HAWAII_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| head | External 647-entry package C | New | SIGN_HEAD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| headache | External 647-entry package C | New | SIGN_HEADACHE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| health | External 647-entry package C | New | SIGN_HEALTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| heaven | External 647-entry package C | New | SIGN_HEAVEN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| heavy | External 647-entry package C | New | SIGN_HEAVY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| helmet | External 647-entry package C | New | SIGN_HELMET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| history | External 647-entry package C | New | SIGN_HISTORY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hockey | External 647-entry package C | New | SIGN_HOCKEY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| homework | External 647-entry package C | New | SIGN_HOMEWORK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| honest | External 647-entry package C | New | SIGN_HONEST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| honor | External 647-entry package C | New | SIGN_HONOR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hope | External 647-entry package C | New | SIGN_HOPE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| horse | External 647-entry package C | New | SIGN_HORSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hunt | External 647-entry package C | New | SIGN_HUNT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hurricane | External 647-entry package C | New | SIGN_HURRICANE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hurry | External 647-entry package C | New | SIGN_HURRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| idea | External 647-entry package C | New | SIGN_IDEA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| impact | External 647-entry package C | New | SIGN_IMPACT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| impossible | External 647-entry package C | New | SIGN_IMPOSSIBLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| innocent | External 647-entry package C | New | SIGN_INNOCENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| inside | External 647-entry package C | New | SIGN_INSIDE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| insurance | External 647-entry package C | New | SIGN_INSURANCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| internet | External 647-entry package C | New | SIGN_INTERNET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| introduce | External 647-entry package C | New | SIGN_INTRODUCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| invite | External 647-entry package C | New | SIGN_INVITE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| italy | External 647-entry package C | New | SIGN_ITALY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| japan | External 647-entry package C | New | SIGN_JAPAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| jealous | External 647-entry package C | New | SIGN_JEALOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| jewish | External 647-entry package C | New | SIGN_JEWISH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| join | External 647-entry package C | New | SIGN_JOIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| joke | External 647-entry package C | New | SIGN_JOKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| journey | External 647-entry package C | New | SIGN_JOURNEY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| jump | External 647-entry package C | New | SIGN_JUMP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| keyboard | External 647-entry package C | New | SIGN_KEYBOARD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| label | External 647-entry package C | New | SIGN_LABEL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lamp | External 647-entry package C | New | SIGN_LAMP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| law | External 647-entry package C | New | SIGN_LAW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lawyer | External 647-entry package C | New | SIGN_LAWYER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lazy | External 647-entry package C | New | SIGN_LAZY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| leak | External 647-entry package C | New | SIGN_LEAK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| less | External 647-entry package C | New | SIGN_LESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lettuce | External 647-entry package C | New | SIGN_LETTUCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| license | External 647-entry package C | New | SIGN_LICENSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lie | External 647-entry package C | New | SIGN_LIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lipstick | External 647-entry package C | New | SIGN_LIPSTICK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lobster | External 647-entry package C | New | SIGN_LOBSTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lock | External 647-entry package C | New | SIGN_LOCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lonely | External 647-entry package C | New | SIGN_LONELY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lousy | External 647-entry package C | New | SIGN_LOUSY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lucky | External 647-entry package C | New | SIGN_LUCKY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| magazine | External 647-entry package C | New | SIGN_MAGAZINE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| marry | External 647-entry package C | New | SIGN_MARRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| math | External 647-entry package C | New | SIGN_MATH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| maybe | External 647-entry package C | New | SIGN_MAYBE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| meeting | External 647-entry package C | New | SIGN_MEETING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| member | External 647-entry package C | New | SIGN_MEMBER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| memorize | External 647-entry package C | New | SIGN_MEMORIZE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| microwave | External 647-entry package C | New | SIGN_MICROWAVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| misunderstand | External 647-entry package C | New | SIGN_MISUNDERSTAND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mock | External 647-entry package C | New | SIGN_MOCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| monkey | External 647-entry package C | New | SIGN_MONKEY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| monster | External 647-entry package C | New | SIGN_MONSTER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| moon | External 647-entry package C | New | SIGN_MOON_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| movie | External 647-entry package C | New | SIGN_MOVIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| music | External 647-entry package C | New | SIGN_MUSIC_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| napkin | External 647-entry package C | New | SIGN_NAPKIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| negative | External 647-entry package C | New | SIGN_NEGATIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| nephew | External 647-entry package C | New | SIGN_NEPHEW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| never | External 647-entry package C | New | SIGN_NEVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| newspaper | External 647-entry package C | New | SIGN_NEWSPAPER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| niece | External 647-entry package C | New | SIGN_NIECE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| normal | External 647-entry package C | New | SIGN_NORMAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| north | External 647-entry package C | New | SIGN_NORTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| obsess | External 647-entry package C | New | SIGN_OBSESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| off | External 647-entry package C | New | SIGN_OFF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| on | External 647-entry package C | New | SIGN_ON_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| other | External 647-entry package C | New | SIGN_OTHER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| outside | External 647-entry package C | New | SIGN_OUTSIDE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| over | External 647-entry package C | New | SIGN_OVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| overlook | External 647-entry package C | New | SIGN_OVERLOOK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| owl | External 647-entry package C | New | SIGN_OWL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pack | External 647-entry package C | New | SIGN_PACK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| paint | External 647-entry package C | New | SIGN_PAINT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| parade | External 647-entry package C | New | SIGN_PARADE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pass | External 647-entry package C | New | SIGN_PASS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pepper | External 647-entry package C | New | SIGN_PEPPER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| perfect | External 647-entry package C | New | SIGN_PERFECT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| perspective | External 647-entry package C | New | SIGN_PERSPECTIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| piano | External 647-entry package C | New | SIGN_PIANO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| picture | External 647-entry package C | New | SIGN_PICTURE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pie | External 647-entry package C | New | SIGN_PIE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pink | External 647-entry package C | New | SIGN_PINK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pity | External 647-entry package C | New | SIGN_PITY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| place | External 647-entry package C | New | SIGN_PLACE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plan | External 647-entry package C | New | SIGN_PLAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plant | External 647-entry package C | New | SIGN_PLANT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plate | External 647-entry package C | New | SIGN_PLATE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plenty | External 647-entry package C | New | SIGN_PLENTY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| plus | External 647-entry package C | New | SIGN_PLUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| point | External 647-entry package C | New | SIGN_POINT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| poop | External 647-entry package C | New | SIGN_POOP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| popular | External 647-entry package C | New | SIGN_POPULAR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| postpone | External 647-entry package C | New | SIGN_POSTPONE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| potato | External 647-entry package C | New | SIGN_POTATO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| power | External 647-entry package C | New | SIGN_POWER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| precious | External 647-entry package C | New | SIGN_PRECIOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| president | External 647-entry package C | New | SIGN_PRESIDENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| price | External 647-entry package C | New | SIGN_PRICE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| print | External 647-entry package C | New | SIGN_PRINT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| promote | External 647-entry package C | New | SIGN_PROMOTE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pull | External 647-entry package C | New | SIGN_PULL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| purple | External 647-entry package C | New | SIGN_PURPLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| push | External 647-entry package C | New | SIGN_PUSH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| put | External 647-entry package C | New | SIGN_PUT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| queen | External 647-entry package C | New | SIGN_QUEEN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| quiet | External 647-entry package C | New | SIGN_QUIET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| race | External 647-entry package C | New | SIGN_RACE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rake | External 647-entry package C | New | SIGN_RAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| really | External 647-entry package C | New | SIGN_REALLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| red | External 647-entry package C | New | SIGN_RED_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| refuse | External 647-entry package C | New | SIGN_REFUSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| relationship | External 647-entry package C | New | SIGN_RELATIONSHIP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| request | External 647-entry package C | New | SIGN_REQUEST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| research | External 647-entry package C | New | SIGN_RESEARCH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| responsibility | External 647-entry package C | New | SIGN_RESPONSIBILITY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| result | External 647-entry package C | New | SIGN_RESULT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rob | External 647-entry package C | New | SIGN_ROB_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rock | External 647-entry package C | New | SIGN_ROCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rude | External 647-entry package C | New | SIGN_RUDE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ruin | External 647-entry package C | New | SIGN_RUIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| salad | External 647-entry package C | New | SIGN_SALAD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sandwich | External 647-entry package C | New | SIGN_SANDWICH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| scared | External 647-entry package C | New | SIGN_SCARED_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| schedule | External 647-entry package C | New | SIGN_SCHEDULE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| scold | External 647-entry package C | New | SIGN_SCOLD_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| scream | External 647-entry package C | New | SIGN_SCREAM_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| screwdriver | External 647-entry package C | New | SIGN_SCREWDRIVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| secretary | External 647-entry package C | New | SIGN_SECRETARY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sensitive | External 647-entry package C | New | SIGN_SENSITIVE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sentence | External 647-entry package C | New | SIGN_SENTENCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| serious | External 647-entry package C | New | SIGN_SERIOUS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sew | External 647-entry package C | New | SIGN_SEW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sheep | External 647-entry package C | New | SIGN_SHEEP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shelf | External 647-entry package C | New | SIGN_SHELF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shirt | External 647-entry package C | New | SIGN_SHIRT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shovel | External 647-entry package C | New | SIGN_SHOVEL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| show | External 647-entry package C | New | SIGN_SHOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| silly | External 647-entry package C | New | SIGN_SILLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| since | External 647-entry package C | New | SIGN_SINCE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| skill | External 647-entry package C | New | SIGN_SKILL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| skin | External 647-entry package C | New | SIGN_SKIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| smart | External 647-entry package C | New | SIGN_SMART_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| smile | External 647-entry package C | New | SIGN_SMILE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| smooth | External 647-entry package C | New | SIGN_SMOOTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| snake | External 647-entry package C | New | SIGN_SNAKE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| snow | External 647-entry package C | New | SIGN_SNOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| soccer | External 647-entry package C | New | SIGN_SOCCER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sofa | External 647-entry package C | New | SIGN_SOFA_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| soft | External 647-entry package C | New | SIGN_SOFT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sound | External 647-entry package C | New | SIGN_SOUND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| soup | External 647-entry package C | New | SIGN_SOUP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| spider | External 647-entry package C | New | SIGN_SPIDER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| spoon | External 647-entry package C | New | SIGN_SPOON_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| spring | External 647-entry package C | New | SIGN_SPRING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| square | External 647-entry package C | New | SIGN_SQUARE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| squirrel | External 647-entry package C | New | SIGN_SQUIRREL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| staff | External 647-entry package C | New | SIGN_STAFF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stairs | External 647-entry package C | New | SIGN_STAIRS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stamp | External 647-entry package C | New | SIGN_STAMP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stare | External 647-entry package C | New | SIGN_STARE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| steal | External 647-entry package C | New | SIGN_STEAL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sting | External 647-entry package C | New | SIGN_STING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stir | External 647-entry package C | New | SIGN_STIR_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| straight | External 647-entry package C | New | SIGN_STRAIGHT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| strange | External 647-entry package C | New | SIGN_STRANGE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stress | External 647-entry package C | New | SIGN_STRESS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| struggle | External 647-entry package C | New | SIGN_STRUGGLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stuck | External 647-entry package C | New | SIGN_STUCK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sunrise | External 647-entry package C | New | SIGN_SUNRISE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| surgery | External 647-entry package C | New | SIGN_SURGERY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| surprise | External 647-entry package C | New | SIGN_SURPRISE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| swallow | External 647-entry package C | New | SIGN_SWALLOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sweet | External 647-entry package C | New | SIGN_SWEET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| swing | External 647-entry package C | New | SIGN_SWING_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tan | External 647-entry package C | New | SIGN_TAN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tennis | External 647-entry package C | New | SIGN_TENNIS_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| test | External 647-entry package C | New | SIGN_TEST_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| therapy | External 647-entry package C | New | SIGN_THERAPY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thermometer | External 647-entry package C | New | SIGN_THERMOMETER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thin | External 647-entry package C | New | SIGN_THIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thirsty | External 647-entry package C | New | SIGN_THIRSTY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| three | External 647-entry package C | New | SIGN_THREE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| throw | External 647-entry package C | New | SIGN_THROW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thursday | External 647-entry package C | New | SIGN_THURSDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tissue | External 647-entry package C | New | SIGN_TISSUE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tobacco | External 647-entry package C | New | SIGN_TOBACCO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| toilet | External 647-entry package C | New | SIGN_TOILET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tomato | External 647-entry package C | New | SIGN_TOMATO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| top | External 647-entry package C | New | SIGN_TOP_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tornado | External 647-entry package C | New | SIGN_TORNADO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| touch | External 647-entry package C | New | SIGN_TOUCH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tournament | External 647-entry package C | New | SIGN_TOURNAMENT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| towel | External 647-entry package C | New | SIGN_TOWEL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| train | External 647-entry package C | New | SIGN_TRAIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| transfer | External 647-entry package C | New | SIGN_TRANSFER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| trouble | External 647-entry package C | New | SIGN_TROUBLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| truth | External 647-entry package C | New | SIGN_TRUTH_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| turtle | External 647-entry package C | New | SIGN_TURTLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| two | External 647-entry package C | New | SIGN_TWO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ugly | External 647-entry package C | New | SIGN_UGLY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| uncle | External 647-entry package C | New | SIGN_UNCLE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| unique | External 647-entry package C | New | SIGN_UNIQUE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| vampire | External 647-entry package C | New | SIGN_VAMPIRE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| verb | External 647-entry package C | New | SIGN_VERB_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| violin | External 647-entry package C | New | SIGN_VIOLIN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| visualize | External 647-entry package C | New | SIGN_VISUALIZE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| voice | External 647-entry package C | New | SIGN_VOICE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| volunteer | External 647-entry package C | New | SIGN_VOLUNTEER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| vote | External 647-entry package C | New | SIGN_VOTE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| waiter | External 647-entry package C | New | SIGN_WAITER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wall | External 647-entry package C | New | SIGN_WALL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wander | External 647-entry package C | New | SIGN_WANDER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| warn | External 647-entry package C | New | SIGN_WARN_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| weak | External 647-entry package C | New | SIGN_WEAK_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| weather | External 647-entry package C | New | SIGN_WEATHER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wednesday | External 647-entry package C | New | SIGN_WEDNESDAY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| weight | External 647-entry package C | New | SIGN_WEIGHT_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wet | External 647-entry package C | New | SIGN_WET_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| whatever | External 647-entry package C | New | SIGN_WHATEVER_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| will | External 647-entry package C | New | SIGN_WILL_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wind | External 647-entry package C | New | SIGN_WIND_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wine | External 647-entry package C | New | SIGN_WINE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wolf | External 647-entry package C | New | SIGN_WOLF_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| worry | External 647-entry package C | New | SIGN_WORRY_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| worse | External 647-entry package C | New | SIGN_WORSE_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| yellow | External 647-entry package C | New | SIGN_YELLOW_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| young | External 647-entry package C | New | SIGN_YOUNG_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| zero | External 647-entry package C | New | SIGN_ZERO_3DLEX_ASL_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |

## Subsequent official 3D-LEX extensions — complete list

| Word | Original Source | New or Existing | Animation Source | Playback Status | ASL Validation |
|---|---|---|---|---|---|
| address | Official 3D-LEX extension after three-source integration | New | SIGN_ADDRESS_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| against | Official 3D-LEX extension after three-source integration | New | SIGN_AGAINST_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| alone | Official 3D-LEX extension after three-source integration | New | SIGN_ALONE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| always | Official 3D-LEX extension after three-source integration | New | SIGN_ALWAYS_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| angry | Official 3D-LEX extension after three-source integration | New | SIGN_ANGRY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| appear | Official 3D-LEX extension after three-source integration | New | SIGN_APPEAR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| area | Official 3D-LEX extension after three-source integration | New | SIGN_AREA_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| argue | Official 3D-LEX extension after three-source integration | New | SIGN_ARGUE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| army | Official 3D-LEX extension after three-source integration | New | SIGN_ARMY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| audience | Official 3D-LEX extension after three-source integration | New | SIGN_AUDIENCE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| avoid | Official 3D-LEX extension after three-source integration | New | SIGN_AVOID_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| balloon | Official 3D-LEX extension after three-source integration | New | SIGN_BALLOON_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bar | Official 3D-LEX extension after three-source integration | New | SIGN_BAR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bath | Official 3D-LEX extension after three-source integration | New | SIGN_BATH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bear | Official 3D-LEX extension after three-source integration | New | SIGN_BEAR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| behind | Official 3D-LEX extension after three-source integration | New | SIGN_BEHIND_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| bicycle | Official 3D-LEX extension after three-source integration | New | SIGN_BICYCLE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| birth | Official 3D-LEX extension after three-source integration | New | SIGN_BIRTH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| break | Official 3D-LEX extension after three-source integration | New | SIGN_BREAK_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| butterfly | Official 3D-LEX extension after three-source integration | New | SIGN_BUTTERFLY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| complex | Official 3D-LEX extension after three-source integration | New | SIGN_COMPLEX_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| danger | Official 3D-LEX extension after three-source integration | New | SIGN_DANGER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| deer | Official 3D-LEX extension after three-source integration | New | SIGN_DEER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| dormitory | Official 3D-LEX extension after three-source integration | New | SIGN_DORMITORY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| dream | Official 3D-LEX extension after three-source integration | New | SIGN_DREAM_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| drug | Official 3D-LEX extension after three-source integration | New | SIGN_DRUG_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| dry | Official 3D-LEX extension after three-source integration | New | SIGN_DRY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| end | Official 3D-LEX extension after three-source integration | New | SIGN_END_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| enter | Official 3D-LEX extension after three-source integration | New | SIGN_ENTER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| expect | Official 3D-LEX extension after three-source integration | New | SIGN_EXPECT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| expert | Official 3D-LEX extension after three-source integration | New | SIGN_EXPERT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| fight | Official 3D-LEX extension after three-source integration | New | SIGN_FIGHT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| fish | Official 3D-LEX extension after three-source integration | New | SIGN_FISH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| forest | Official 3D-LEX extension after three-source integration | New | SIGN_FOREST_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| friendly | Official 3D-LEX extension after three-source integration | New | SIGN_FRIENDLY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| full | Official 3D-LEX extension after three-source integration | New | SIGN_FULL_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| gamble | Official 3D-LEX extension after three-source integration | New | SIGN_GAMBLE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| gloves | Official 3D-LEX extension after three-source integration | New | SIGN_GLOVES_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| happen | Official 3D-LEX extension after three-source integration | New | SIGN_HAPPEN_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| hide | Official 3D-LEX extension after three-source integration | New | SIGN_HIDE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| hurt | Official 3D-LEX extension after three-source integration | New | SIGN_HURT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| improve | Official 3D-LEX extension after three-source integration | New | SIGN_IMPROVE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| iron | Official 3D-LEX extension after three-source integration | New | SIGN_IRON_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| knife | Official 3D-LEX extension after three-source integration | New | SIGN_KNIFE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| laptop | Official 3D-LEX extension after three-source integration | New | SIGN_LAPTOP_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| late | Official 3D-LEX extension after three-source integration | New | SIGN_LATE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| lecture | Official 3D-LEX extension after three-source integration | New | SIGN_LECTURE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| long | Official 3D-LEX extension after three-source integration | New | SIGN_LONG_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| mad | Official 3D-LEX extension after three-source integration | New | SIGN_MAD_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| mirror | Official 3D-LEX extension after three-source integration | New | SIGN_MIRROR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| mouse | Official 3D-LEX extension after three-source integration | New | SIGN_MOUSE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| mouth | Official 3D-LEX extension after three-source integration | New | SIGN_MOUTH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| necklace | Official 3D-LEX extension after three-source integration | New | SIGN_NECKLACE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| next | Official 3D-LEX extension after three-source integration | New | SIGN_NEXT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| nose | Official 3D-LEX extension after three-source integration | New | SIGN_NOSE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| ocean | Official 3D-LEX extension after three-source integration | New | SIGN_OCEAN_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| past | Official 3D-LEX extension after three-source integration | New | SIGN_PAST_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| pride | Official 3D-LEX extension after three-source integration | New | SIGN_PRIDE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| punish | Official 3D-LEX extension after three-source integration | New | SIGN_PUNISH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| puzzled | Official 3D-LEX extension after three-source integration | New | SIGN_PUZZLED_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| relax | Official 3D-LEX extension after three-source integration | New | SIGN_RELAX_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| rich | Official 3D-LEX extension after three-source integration | New | SIGN_RICH_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| share | Official 3D-LEX extension after three-source integration | New | SIGN_SHARE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| sing | Official 3D-LEX extension after three-source integration | New | SIGN_SING_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| smell | Official 3D-LEX extension after three-source integration | New | SIGN_SMELL_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| soap | Official 3D-LEX extension after three-source integration | New | SIGN_SOAP_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| sour | Official 3D-LEX extension after three-source integration | New | SIGN_SOUR_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| stubborn | Official 3D-LEX extension after three-source integration | New | SIGN_STUBBORN_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| summer | Official 3D-LEX extension after three-source integration | New | SIGN_SUMMER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| suspect | Official 3D-LEX extension after three-source integration | New | SIGN_SUSPECT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| sweetheart | Official 3D-LEX extension after three-source integration | New | SIGN_SWEETHEART_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| text | Official 3D-LEX extension after three-source integration | New | SIGN_TEXT_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| tiger | Official 3D-LEX extension after three-source integration | New | SIGN_TIGER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| traffic | Official 3D-LEX extension after three-source integration | New | SIGN_TRAFFIC_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| under | Official 3D-LEX extension after three-source integration | New | SIGN_UNDER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| up | Official 3D-LEX extension after three-source integration | New | SIGN_UP_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| way | Official 3D-LEX extension after three-source integration | New | SIGN_WAY_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| we | Official 3D-LEX extension after three-source integration | New | SIGN_WE_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| wonder | Official 3D-LEX extension after three-source integration | New | SIGN_WONDER_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| wood | Official 3D-LEX extension after three-source integration | New | SIGN_WOOD_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |
| wow | Official 3D-LEX extension after three-source integration | New | SIGN_WOW_3DLEX_ASL_PREVIEW | Android native selection, rendered samples and continuous completion recorded | Requires qualified ASL validation |

## Entries already in the target branch — complete list

| Word | Original Source | New or Existing | Animation Source | Playback Status | ASL Validation |
|---|---|---|---|---|---|
| afternoon | Target branch A (working motion retained where changed) | Existing | SIGN_AFTERNOON | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| again | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_AGAIN_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| all | Target branch A (working motion retained where changed) | Existing | SIGN_ALL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| any | Target branch A (working motion retained where changed) | Existing | SIGN_ANY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ask | Target branch A (working motion retained where changed) | Existing | SIGN_ASK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| baby | Target branch A (working motion retained where changed) | Existing | SIGN_BABY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bad | Target branch A (working motion retained where changed) | Existing | SIGN_BAD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bag | Target branch A (working motion retained where changed) | Existing | SIGN_BAG | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| be | Target branch A (working motion retained where changed) | Existing | SIGN_BE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| beautiful | Target branch A (working motion retained where changed) | Existing | SIGN_BEAUTIFUL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| become | Target branch A (working motion retained where changed) | Existing | SIGN_BECOME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bed | Target branch A (working motion retained where changed) | Existing | SIGN_BED | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| begin | Target branch A (working motion retained where changed) | Existing | SIGN_BEGIN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| best | Target branch A (working motion retained where changed) | Existing | SIGN_BEST_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| better | Target branch A (working motion retained where changed) | Existing | SIGN_BETTER_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| big | Target branch A (working motion retained where changed) | Existing | SIGN_BIG | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| book | Target branch A (working motion retained where changed) | Existing | SIGN_BOOK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| boss | Target branch A (working motion retained where changed) | Existing | SIGN_BOSS | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| brother | Target branch A (working motion retained where changed) | Existing | SIGN_BROTHER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| busy | Target branch A (working motion retained where changed) | Existing | SIGN_BUSY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| buy | Target branch A (working motion retained where changed) | Existing | SIGN_BUY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| bye | Target branch A (working motion retained where changed) | Existing | SIGN_BYE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| call | Target branch A (working motion retained where changed) | Existing | SIGN_CALL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| call someones name | Target branch A (working motion retained where changed) | Existing | SIGN_CALL__TO_CALL_SOMEONE_S_NAME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| car | Target branch A (working motion retained where changed) | Existing | SIGN_CAR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| chair | Target branch A (working motion retained where changed) | Existing | SIGN_CHAIR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| child | Target branch A (working motion retained where changed) | Existing | SIGN_CHILD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| city | Target branch A (working motion retained where changed) | Existing | SIGN_CITY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| class | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_CLASS_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clean | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_CLEAN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| close | Target branch A (working motion retained where changed) | Existing | SIGN_CLOSE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clothes | Target branch A (working motion retained where changed) | Existing | SIGN_CLOTHES | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cold | Target branch A (working motion retained where changed) | Existing | SIGN_COLD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| come | Target branch A (working motion retained where changed) | Existing | SIGN_COME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| computer | Target branch A (working motion retained where changed) | Existing | SIGN_COMPUTER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| congratulations | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_CONGRATULATIONS | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| cook | Target branch A (working motion retained where changed) | Existing | SIGN_COOK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| country | Target branch A (working motion retained where changed) | Existing | SIGN_COUNTRY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| day | Target branch A (working motion retained where changed) | Existing | SIGN_DAY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deaf | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_DEAF_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| different | Target branch A (working motion retained where changed) | Existing | SIGN_DIFFERENT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| divorce | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_DIVORCE_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| do | Target branch A (working motion retained where changed) | Existing | SIGN_DO | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| door | Target branch A (working motion retained where changed) | Existing | SIGN_DOOR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| drink | Target branch A (working motion retained where changed) | Existing | SIGN_DRINK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| drive | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_DRIVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| easy | Target branch A (working motion retained where changed) | Existing | SIGN_EASY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| eat | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_EAT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| evening | Target branch A (working motion retained where changed) | Existing | SIGN_EVENING | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| every | Target branch A (working motion retained where changed) | Existing | SIGN_EVERY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| excuse me | Target branch A (working motion retained where changed) | Existing | SIGN_EXCUSE_ME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| exhausted | Target branch A (working motion retained where changed) | Existing | SIGN_EXHAUSTED | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| family | Target branch A (working motion retained where changed) | Existing | SIGN_FAMILY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fast | Target branch A (working motion retained where changed) | Existing | SIGN_FAST | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| father | Target branch A (working motion retained where changed) | Existing | SIGN_FATHER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| feel | Target branch A (working motion retained where changed) | Existing | SIGN_FEEL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| few | Target branch A (working motion retained where changed) | Existing | SIGN_FEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| find | Target branch A (working motion retained where changed) | Existing | SIGN_FIND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| fingerspell | Target branch A (working motion retained where changed) | Existing | SIGN_FINGERSPELL_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| finish | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_FINISH_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| free | Target branch A (working motion retained where changed) | Existing | SIGN_FREE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| friend | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_FRIEND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| from | Target branch A (working motion retained where changed) | Existing | SIGN_FROM_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| get | Target branch A (working motion retained where changed) | Existing | SIGN_GET | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| give | Target branch A (working motion retained where changed) | Existing | SIGN_GIVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| go | Target branch A (working motion retained where changed) | Existing | SIGN_GO | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| good | Target branch A (working motion retained where changed) | Existing | SIGN_GOOD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grandma | Target branch A (working motion retained where changed) | Existing | SIGN_GRANDMA_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grandpa | Target branch A (working motion retained where changed) | Existing | SIGN_GRANDPA_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| grow up | Target branch A (working motion retained where changed) | Existing | SIGN_GROW_UP_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| happy | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HAPPY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hard | Target branch A (working motion retained where changed) | Existing | SIGN_HARD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hard solid | Target branch A (working motion retained where changed) | Existing | SIGN_HARD__SOLID | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| have | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HAVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| he / she | Target branch A (working motion retained where changed) | Existing | SIGN_HE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hear | Target branch A (working motion retained where changed) | Existing | SIGN_HEAR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hearing | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HEARING_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hello | Target branch A (working motion retained where changed) | Existing | SIGN_HELLO | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| help | Target branch A (working motion retained where changed) | Existing | SIGN_HELP | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| here | Target branch A (working motion retained where changed) | Existing | SIGN_HERE_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| home | Target branch A (working motion retained where changed) | Existing | SIGN_HOME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hospital | Target branch A (working motion retained where changed) | Existing | SIGN_HOSPITAL | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| hot | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HOT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hour | Target branch A (working motion retained where changed) | Existing | SIGN_HOUR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| house | Target branch A (working motion retained where changed) | Existing | SIGN_HOUSE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| how | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HOW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hungry | Target branch A (working motion retained where changed) | Existing | SIGN_HUNGRY_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| husband | Target branch A (working motion retained where changed) | Existing | SIGN_HUSBAND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| i / me | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_I | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| important | Target branch A (working motion retained where changed) | Existing | SIGN_IMPORTANT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| in | Target branch A (working motion retained where changed) | Existing | SIGN_IN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| keep | Target branch A (working motion retained where changed) | Existing | SIGN_KEEP | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| keep preserve | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_KEEP__PRESERVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| key | Target branch A (working motion retained where changed) | Existing | SIGN_KEY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| know | Target branch A (working motion retained where changed) | Existing | SIGN_KNOW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| lady / woman | Target branch A (working motion retained where changed) | Existing | SIGN_WOMAN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| learn | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_LEARN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| leave | Target branch A (working motion retained where changed) | Existing | SIGN_LEAVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| let | Target branch A (working motion retained where changed) | Existing | SIGN_LET | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| letter | Target branch A (working motion retained where changed) | Existing | SIGN_LETTER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| letter mail | Target branch A (working motion retained where changed) | Existing | SIGN_LETTER__MAIL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| like / affection / for | Target branch A (working motion retained where changed) | Existing | SIGN_LIKE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| listen | Target branch A (working motion retained where changed) | Existing | SIGN_LISTEN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| little / small | Target branch A (working motion retained where changed) | Existing | SIGN_LITTLE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| live | Target branch A (working motion retained where changed) | Existing | SIGN_LIVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| look | Target branch A (working motion retained where changed) | Existing | SIGN_LOOK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| love | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_LOVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| make | Target branch A (working motion retained where changed) | Existing | SIGN_MAKE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| male / boy / dude / guy / fellow | Target branch A (working motion retained where changed) | Existing | SIGN_GUY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| man | Target branch A (working motion retained where changed) | Existing | SIGN_MAN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| many | Target branch A (working motion retained where changed) | Existing | SIGN_MANY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mean | Target branch A (working motion retained where changed) | Existing | SIGN_MEAN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mean meaning | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_MEAN__MEANING_OR_DEFINITION_OF_SOMETHING | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| meet | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_MEET | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| meet many people | Target branch A (working motion retained where changed) | Existing | SIGN_MEET__TO_MEET_MANY_PEOPLE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| minute | Target branch A (working motion retained where changed) | Existing | SIGN_MINUTE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| moment | Target branch A (working motion retained where changed) | Existing | SIGN_MOMENT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| money | Target branch A (working motion retained where changed) | Existing | SIGN_MONEY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| month | Target branch A (working motion retained where changed) | Existing | SIGN_MONTH | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| more | Target branch A (working motion retained where changed) | Existing | SIGN_MORE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| morning | Target branch A (working motion retained where changed) | Existing | SIGN_MORNING | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| most | Target branch A (working motion retained where changed) | Existing | SIGN_MOST | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mother | Target branch A (working motion retained where changed) | Existing | SIGN_MOTHER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| move | Target branch A (working motion retained where changed) | Existing | SIGN_MOVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| move new location | Target branch A (working motion retained where changed) | Existing | SIGN_MOVE__TO_MOVE_TO_NEW_LOCATION | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| much | Target branch A (working motion retained where changed) | Existing | SIGN_MUCH | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| must | Target branch A (working motion retained where changed) | Existing | SIGN_MUST_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| my / mine | Target branch A (working motion retained where changed) | Existing | SIGN_MY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| name | Target branch A (working motion retained where changed) | Existing | SIGN_CALL__TO_CALL_SOMEONE_S_NAME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| need | Target branch A (working motion retained where changed) | Existing | SIGN_NEED | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| neighbor | Target branch A (working motion retained where changed) | Existing | SIGN_NEIGHBOR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| new | Target branch A (working motion retained where changed) | Existing | SIGN_NEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| no | Target branch A (working motion retained where changed) | Existing | SIGN_NO | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| now | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_NOW_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| office | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_OFFICE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ok | Target branch A (working motion retained where changed) | Existing | SIGN_OK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| old | Target branch A (working motion retained where changed) | Existing | SIGN_OLD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| open | Target branch A (working motion retained where changed) | Existing | SIGN_OPEN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| our | Target branch A (working motion retained where changed) | Existing | SIGN_OUR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| paper | Target branch A (working motion retained where changed) | Existing | SIGN_PAPER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| parents | Target branch A (working motion retained where changed) | Existing | SIGN_PARENTS_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pay | Target branch A (working motion retained where changed) | Existing | SIGN_PAY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| pay someone | Target branch A (working motion retained where changed) | Existing | SIGN_PAY__TO_PAY_SOMEONE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| people | Target branch A (working motion retained where changed) | Existing | SIGN_PEOPLE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| person | Target branch A (working motion retained where changed) | Existing | SIGN_PERSON | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| phone | Target branch A (working motion retained where changed) | Existing | SIGN_PHONE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| play | Target branch A (working motion retained where changed) | Existing | SIGN_PLAY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| play a game | Target branch A (working motion retained where changed) | Existing | SIGN_PLAY__TO_PLAY_A_GAME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| please | Target branch A (working motion retained where changed) | Existing | SIGN_PLEASE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| prefer | Target branch A (working motion retained where changed) | Existing | SIGN_PREFER_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| rain | Target branch A (working motion retained where changed) | Existing | SIGN_RAIN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| read | Target branch A (working motion retained where changed) | Existing | SIGN_READ | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| ready | Target branch A (working motion retained where changed) | Existing | SIGN_READY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| restaurant | Target branch A (working motion retained where changed) | Existing | SIGN_RESTAURANT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| right | Target branch A (working motion retained where changed) | Existing | SIGN_RIGHT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| right direction | Target branch A (working motion retained where changed) | Existing | SIGN_RIGHT__DIRECTION | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| road | Target branch A (working motion retained where changed) | Existing | SIGN_ROAD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| room | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_ROOM | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| run | Target branch A (working motion retained where changed) | Existing | SIGN_RUN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sad | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_SAD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| same | Target branch A (working motion retained where changed) | Existing | SIGN_SAME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| school | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_SCHOOL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| see | Target branch A (working motion retained where changed) | Existing | SIGN_SEE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| seem | Target branch A (working motion retained where changed) | Existing | SIGN_SEEM | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sell | Target branch A (working motion retained where changed) | Existing | SIGN_SELL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| send | Target branch A (working motion retained where changed) | Existing | SIGN_SEND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shoes | Target branch A (working motion retained where changed) | Existing | SIGN_SHOES | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| shop | Target branch A (working motion retained where changed) | Existing | SIGN_SHOP__GOING_TO_STORE_TO_BUY_GOODS | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| show someone | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_SHOW__TO_SHOW_SOMEONE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sick | Target branch A (working motion retained where changed) | Existing | SIGN_SICK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| single | Target branch A (working motion retained where changed) | Existing | SIGN_SINGLE_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sister | Target branch A (working motion retained where changed) | Existing | SIGN_SISTER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sit | Target branch A (working motion retained where changed) | Existing | SIGN_SIT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sleep | Target branch A (working motion retained where changed) | Existing | SIGN_SLEEP | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| slow | Target branch A (working motion retained where changed) | Existing | SIGN_SLOW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| so so | Target branch A (working motion retained where changed) | Existing | SIGN_SO_SO_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| some | Target branch A (working motion retained where changed) | Existing | SIGN_SOME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sorry | Target branch A (working motion retained where changed) | Existing | SIGN_SORRY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| speak | Target branch A (working motion retained where changed) | Existing | SIGN_SPEAK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stay | Target branch A (working motion retained where changed) | Existing | SIGN_STAY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| stop | Target branch A (working motion retained where changed) | Existing | SIGN_STOP_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| store save | Target branch A (working motion retained where changed) | Existing | SIGN_STORE__TO_SAVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| strong | Target branch A (working motion retained where changed) | Existing | SIGN_STRONG | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| student | Target branch A (working motion retained where changed) | Existing | SIGN_STUDENT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sure | Target branch A (working motion retained where changed) | Existing | SIGN_SURE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| table | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TABLE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| take | Target branch A (working motion retained where changed) | Existing | SIGN_TAKE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| teacher | Target branch A (working motion retained where changed) | Existing | SIGN_TEACHER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tell | Target branch A (working motion retained where changed) | Existing | SIGN_TELL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thank you | Target branch A (working motion retained where changed) | Existing | SIGN_THANKS | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| them | Target branch A (working motion retained where changed) | Existing | SIGN_THEM | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| thing | Target branch A (working motion retained where changed) | Existing | SIGN_THING | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| think | Target branch A (working motion retained where changed) | Existing | SIGN_THINK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| time | Target branch A (working motion retained where changed) | Existing | SIGN_TIME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tired | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TIRED_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| today | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TODAY | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| tomorrow | Target branch A (working motion retained where changed) | Existing | SIGN_TOMORROW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| try | Target branch A (working motion retained where changed) | Existing | SIGN_TRY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| turn | Target branch A (working motion retained where changed) | Existing | SIGN_TURN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| turn around | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TURN__TURN_AROUND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| understand | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_UNDERSTAND_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| us | Target branch A (working motion retained where changed) | Existing | SIGN_US | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| use | Target branch A (working motion retained where changed) | Existing | SIGN_USE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| visit | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_VISIT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wait | Target branch A (working motion retained where changed) | Existing | SIGN_WAIT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wake | Target branch A (working motion retained where changed) | Existing | SIGN_WAKE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| walk | Target branch A (working motion retained where changed) | Existing | SIGN_WALK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| want | Target branch A (working motion retained where changed) | Existing | SIGN_WANT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wash | Target branch A (working motion retained where changed) | Existing | SIGN_WASH | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| watch | Target branch A (working motion retained where changed) | Existing | SIGN_WATCH | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| water | Target branch A (working motion retained where changed) | Existing | SIGN_WATER | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| week | Target branch A (working motion retained where changed) | Existing | SIGN_WEEK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| welcome | Target branch A (working motion retained where changed) | Existing | SIGN_WELCOME | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| what | Target branch A (working motion retained where changed) | Existing | SIGN_WHAT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| what rhetorical | Target branch A (working motion retained where changed) | Existing | SIGN_WHAT__RHETORICAL_WHAT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| when | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_WHEN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| where | Target branch A (working motion retained where changed) | Existing | SIGN_WHERE | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| which | Target branch A (working motion retained where changed) | Existing | SIGN_WHICH | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| who | Target branch A (working motion retained where changed) | Existing | SIGN_WHO | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| why | Target branch A (working motion retained where changed) | Existing | SIGN_WHY | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| wife | Target branch A (working motion retained where changed) | Existing | SIGN_WIFE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| window | Target branch A (working motion retained where changed) | Existing | SIGN_WINDOW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| work | Target branch A (working motion retained where changed) | Existing | SIGN_WORK | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| world | Target branch A (working motion retained where changed) | Existing | SIGN_WORLD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| write | Target branch A (working motion retained where changed) | Existing | SIGN_WRITE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wrong | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_WRONG | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| year | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_YEAR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| yes | Target branch A (working motion retained where changed) | Existing | SIGN_YES | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| yesterday | Target branch A (working motion retained where changed) | Existing | SIGN_YESTERDAY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| you | Target branch A (working motion retained where changed) | Existing | SIGN_YOU_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| you all | Target branch A (working motion retained where changed) | Existing | SIGN_YOU_ALL_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| your / yours | Target branch A (working motion retained where changed) | Existing | SIGN_YOUR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |

## Target-existing animations changed in the working source

These 36 track changes were retained selectively, with primary rollback actions still packaged. They are not all declared improvements; LOVE/ME and other prior flags remain subject to review.

| Word | Original Source | New or Existing | Animation Source | Playback Status | ASL Validation |
|---|---|---|---|---|---|
| again | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_AGAIN_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| class | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_CLASS_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| clean | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_CLEAN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| congratulations | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_CONGRATULATIONS | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| deaf | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_DEAF_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| divorce | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_DIVORCE_HUMAN_RETARGETED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| drive | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_DRIVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| eat | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_EAT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| finish | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_FINISH_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| friend | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_FRIEND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| happy | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HAPPY | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| have | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HAVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hearing | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HEARING_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| hot | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HOT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| how | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_HOW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| i / me | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_I | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| keep preserve | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_KEEP__PRESERVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| learn | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_LEARN_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| love | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_LOVE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| mean meaning | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_MEAN__MEANING_OR_DEFINITION_OF_SOMETHING | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| meet | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_MEET | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| now | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_NOW_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| office | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_OFFICE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| room | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_ROOM | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| sad | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_SAD | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| school | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_SCHOOL | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| show someone | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_SHOW__TO_SHOW_SOMEONE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| table | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TABLE | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| tired | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TIRED_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| today | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TODAY | Prior Android native playback observed; see integration inventory | Requires qualified ASL validation |
| turn around | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_TURN__TURN_AROUND | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| understand | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_UNDERSTAND_HUMAN_AUTHORED_PREVIEW | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| visit | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_VISIT | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| when | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_WHEN | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| wrong | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_WRONG | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |
| year | Target branch A (working motion retained where changed) | Existing; animation changed | SIGN_YEAR | Offline named-action/mapping checks passed; individual Android playback not established | Requires qualified ASL validation |

## New alias forms vs target branch — complete list

| English alias | Dictionary ID | Motion action |
|---|---|---|
| afraid | scared | SIGN_SCARED_3DLEX_ASL_PREVIEW |
| apparel | clothes | SIGN_CLOTHES |
| assist | help | SIGN_HELP |
| assistance | help | SIGN_HELP |
| auto | car | SIGN_CAR |
| automobile | car | SIGN_CAR |
| behaviour | behavior | SIGN_BEHAVIOR_3DLEX_ASL_PREVIEW |
| carry on | continue | SIGN_CONTINUE_3DLEX_ASL_PREVIEW |
| centre | center | SIGN_CENTER_3DLEX_ASL_PREVIEW |
| clothing | clothes | SIGN_CLOTHES |
| communicating | communicate | SIGN_COMMUNICATE_HUMAN_AUTHORED_PREVIEW |
| comprehend | understand | SIGN_UNDERSTAND_HUMAN_AUTHORED_PREVIEW |
| congrats | congratulations | SIGN_CONGRATULATIONS |
| costly | expensive | SIGN_EXPENSIVE_3DLEX_ASL_PREVIEW |
| daddy | father | SIGN_FATHER |
| delay | postpone | SIGN_POSTPONE_3DLEX_ASL_PREVIEW |
| done | finish | SIGN_FINISH_HUMAN_AUTHORED_PREVIEW |
| e mail | email | SIGN_EMAIL_3DLEX_ASL_PREVIEW |
| eatery | restaurant | SIGN_RESTAURANT |
| employment | work | SIGN_WORK |
| explaining | explain | SIGN_EXPLAIN_HUMAN_AUTHORED_PREVIEW |
| farewell | bye | SIGN_BYE |
| fatigued | tired | SIGN_TIRED_HUMAN_AUTHORED_PREVIEW |
| favourite | prefer | SIGN_PREFER_HUMAN_RETARGETED_PREVIEW |
| film | movie | SIGN_MOVIE_3DLEX_ASL_PREVIEW |
| finger spell | fingerspell | SIGN_FINGERSPELL_HUMAN_RETARGETED_PREVIEW |
| finished | finish | SIGN_FINISH_HUMAN_AUTHORED_PREVIEW |
| food | eat | SIGN_EAT |
| frightened | scared | SIGN_SCARED_3DLEX_ASL_PREVIEW |
| glad | happy | SIGN_HAPPY |
| good bye | bye | SIGN_BYE |
| grandad | grandpa | SIGN_GRANDPA_HUMAN_RETARGETED_PREVIEW |
| granddad | grandpa | SIGN_GRANDPA_HUMAN_RETARGETED_PREVIEW |
| grandmom | grandma | SIGN_GRANDMA_HUMAN_RETARGETED_PREVIEW |
| granny | grandma | SIGN_GRANDMA_HUMAN_RETARGETED_PREVIEW |
| grey | gray | SIGN_GRAY_3DLEX_ASL_PREVIEW |
| grown up | adult | SIGN_ADULT_3DLEX_ASL_PREVIEW |
| grownup | adult | SIGN_ADULT_3DLEX_ASL_PREVIEW |
| halt | stop | SIGN_STOP_HUMAN_AUTHORED_PREVIEW |
| ill | sick | SIGN_SICK |
| illness | sick | SIGN_SICK |
| individual | person | SIGN_PERSON |
| inexpensive | cheap | SIGN_CHEAP_3DLEX_ASL_PREVIEW |
| instructor | teacher | SIGN_TEACHER |
| job | work | SIGN_WORK |
| kid | child | SIGN_CHILD |
| kids | children | SIGN_CHILDREN_3DLEX_ASL_PREVIEW |
| labor | work | SIGN_WORK |
| labour | work | SIGN_WORK |
| lad | male_boy | SIGN_GUY |
| mama | mother | SIGN_MOTHER |
| medical doctor | doctor | SIGN_DOCTOR_HUMAN_AUTHORED_PREVIEW |
| momma | mother | SIGN_MOTHER |
| mommy | mother | SIGN_MOTHER |
| mummy | mother | SIGN_MOTHER |
| neighbour | neighbor | SIGN_NEIGHBOR |
| papa | father | SIGN_FATHER |
| path | road | SIGN_ROAD |
| personal computer | computer | SIGN_COMPUTER |
| persons | people | SIGN_PEOPLE |
| physician | doctor | SIGN_DOCTOR_HUMAN_AUTHORED_PREVIEW |
| pretty | beautiful | SIGN_BEAUTIFUL |
| pupil | student | SIGN_STUDENT |
| purchase | buy | SIGN_BUY |
| quick | fast | SIGN_FAST |
| restroom | bathroom | SIGN_BATHROOM_HUMAN_AUTHORED_PREVIEW |
| sightless | blind | SIGN_BLIND_3DLEX_ASL_PREVIEW |
| sign language | sign | SIGN_SIGN_HUMAN_AUTHORED_PREVIEW |
| signing | sign | SIGN_SIGN_HUMAN_AUTHORED_PREVIEW |
| start | begin | SIGN_BEGIN |
| street | road | SIGN_ROAD |
| studying | study | SIGN_STUDY_HUMAN_AUTHORED_PREVIEW |
| telephone | phone | SIGN_PHONE |
| thankyou | thank_you | SIGN_THANKS |
| uni | university | SIGN_UNIVERSITY_HUMAN_AUTHORED_PREVIEW |
| unwell | sick | SIGN_SICK |
| yall | you_all | SIGN_YOU_ALL_HUMAN_RETARGETED_PREVIEW |

## Phrase and expression distinctions

No newly validated phrase translation was introduced. Multiword lexical labels below each resolve to one named motion; they are not necessarily grammatically complete ASL sentences. The separate everyday registry has 10 CANDIDATE meaning records with empty validated sign/gloss arrays. English word sequences remain labelled previews.

| Multiword input label | ID | Action |
|---|---|---|
| call someones name | call_someones_name | SIGN_CALL__TO_CALL_SOMEONE_S_NAME |
| excuse me | excuse_me | SIGN_EXCUSE_ME |
| grow up | grow_up | SIGN_GROW_UP_HUMAN_RETARGETED_PREVIEW |
| hard solid | hard_solid | SIGN_HARD__SOLID |
| he / she | he_she | SIGN_HE |
| i / me | i_me | SIGN_I |
| keep preserve | keep_preserve | SIGN_KEEP__PRESERVE |
| lady / woman | lady_woman | SIGN_WOMAN |
| letter mail | letter_mail | SIGN_LETTER__MAIL |
| like / affection / for | like_affection_for | SIGN_LIKE |
| little / small | little_small | SIGN_LITTLE |
| male / boy / dude / guy / fellow | male_boy | SIGN_GUY |
| mean meaning | mean_meaning | SIGN_MEAN__MEANING_OR_DEFINITION_OF_SOMETHING |
| meet many people | meet_many_people | SIGN_MEET__TO_MEET_MANY_PEOPLE |
| move new location | move_new_location | SIGN_MOVE__TO_MOVE_TO_NEW_LOCATION |
| my / mine | my_mine | SIGN_MY |
| pay someone | pay_someone | SIGN_PAY__TO_PAY_SOMEONE |
| play a game | play_game | SIGN_PLAY__TO_PLAY_A_GAME |
| right direction | right_direction | SIGN_RIGHT__DIRECTION |
| show someone | show_someone | SIGN_SHOW__TO_SHOW_SOMEONE |
| so so | so_so | SIGN_SO_SO_HUMAN_RETARGETED_PREVIEW |
| store save | store_save | SIGN_STORE__TO_SAVE |
| thank you | thank_you | SIGN_THANKS |
| turn around | turn_around | SIGN_TURN__TURN_AROUND |
| what rhetorical | what_rhetorical | SIGN_WHAT__RHETORICAL_WHAT |
| you all | you_all | SIGN_YOU_ALL_HUMAN_RETARGETED_PREVIEW |
| your / yours | your_yours | SIGN_YOUR |

| Candidate phrase | Status | Validated gloss/sequence |
|---|---|---|
| Hello / Hi / Hey | CANDIDATE | None; not a validated sentence |
| How are you / How are you doing | CANDIDATE | None; not a validated sentence |
| What is your name / Whats your name / What is your name please | CANDIDATE | None; not a validated sentence |
| My name is / My name | CANDIDATE | None; not a validated sentence |
| It is hot today / Its hot today / Today is hot | CANDIDATE | None; not a validated sentence |
| It is raining / Its raining / It is rainy / Its rainy | CANDIDATE | None; not a validated sentence |
| I am hungry / Im hungry / I feel hungry | CANDIDATE | None; not a validated sentence |
| I am tired / Im tired / I feel tired | CANDIDATE | None; not a validated sentence |
| Thank you / Thanks | CANDIDATE | None; not a validated sentence |
| Can you help me / Could you help me / Will you help me / Please help me | CANDIDATE | None; not a validated sentence |

## Missing, rejected or suspect motion data

Every one of the 743 active entries maps to an existing named action. This checks file availability, not all handshapes, body intersections, meanings or ASL variants. NAME reuses an existing CALL-SOMEONE'S-NAME form. Previous LOVE, ME/I and WHY wrist/contact concerns remain flagged. No generic “all words accurate” assertion is made.

All 262 unadded official-source candidates are listed individually below. Duplicate payloads require meaning review; they are not falsely counted as new signs.

| Candidate word | Why not added |
|---|---|
| action | Duplicate source payload; requires sense/variant review |
| actor | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 177.68205586803367) |
| add | Duplicate source payload; requires sense/variant review |
| advantage | Duplicate source payload; requires sense/variant review |
| after | Duplicate source payload; requires sense/variant review |
| airplane | Duplicate source payload; requires sense/variant review |
| alarm | Duplicate source payload; requires sense/variant review |
| analyze | Duplicate source payload; requires sense/variant review |
| angel | ('Bone direction transfer exceeds one degree', 0.06990588544236465) |
| animal | Duplicate source payload; requires sense/variant review |
| announce | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.41901871054984) |
| arrive | ('Bone direction transfer exceeds one degree', 0.02235195588613584) |
| asia | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.35871082820168) |
| attention | Duplicate source payload; requires sense/variant review |
| australia | Duplicate source payload; requires sense/variant review |
| average | Duplicate source payload; requires sense/variant review |
| awake | Duplicate source payload; requires sense/variant review |
| bacon | ('Bone direction transfer exceeds one degree', 0.0466856361056337) |
| banana | Duplicate source payload; requires sense/variant review |
| bank | Duplicate source payload; requires sense/variant review |
| beard | Duplicate source payload; requires sense/variant review |
| believe | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.00468897713603) |
| bird | Duplicate source payload; requires sense/variant review |
| birthday | Duplicate source payload; requires sense/variant review |
| blame | ('Bone direction transfer exceeds one degree', 0.019792917375399927) |
| blood | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.18095552026244) |
| blue | Duplicate source payload; requires sense/variant review |
| boat | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 107.26532548242614) |
| body | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.5793127664155) |
| bored | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.24774924299774) |
| borrow | Duplicate source payload; requires sense/variant review |
| bother | Duplicate source payload; requires sense/variant review |
| box | Duplicate source payload; requires sense/variant review |
| bra | Duplicate source payload; requires sense/variant review |
| bring | Duplicate source payload; requires sense/variant review |
| bug | Duplicate source payload; requires sense/variant review |
| building | Duplicate source payload; requires sense/variant review |
| business | Duplicate source payload; requires sense/variant review |
| butter | Duplicate source payload; requires sense/variant review |
| camping | Duplicate source payload; requires sense/variant review |
| cannot | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 178.37768771523238) |
| carrot | Duplicate source payload; requires sense/variant review |
| carry | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 172.6524323025501) |
| certificate | ('Bone direction transfer exceeds one degree', 0.0320130721802534) |
| chain | Duplicate source payload; requires sense/variant review |
| chance | ('Bone direction transfer exceeds one degree', 0.03431107299774991) |
| check | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.52360848589817) |
| cheese | Duplicate source payload; requires sense/variant review |
| china | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 171.7241155563958) |
| chop | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 130.68724103994893) |
| cigarette | Duplicate source payload; requires sense/variant review |
| circle | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.86057034561892) |
| color | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.8672463510745) |
| community | Duplicate source payload; requires sense/variant review |
| conflict | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.30027522333037) |
| contact | Duplicate source payload; requires sense/variant review |
| cost | Duplicate source payload; requires sense/variant review |
| culture | Duplicate source payload; requires sense/variant review |
| delicious | ('Bone direction transfer exceeds one degree', 0.10738713046510082) |
| demand | ('Bone direction transfer exceeds one degree', 0.07600168731032127) |
| desert | Duplicate source payload; requires sense/variant review |
| dirty | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.381868807869) |
| disconnect | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.83680089506367) |
| discuss | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 172.5595185774049) |
| dissolve | Duplicate source payload; requires sense/variant review |
| divide | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.4106772294383) |
| doll | Duplicate source payload; requires sense/variant review |
| dolphin | Duplicate source payload; requires sense/variant review |
| draw | Duplicate source payload; requires sense/variant review |
| drop | ('Bone direction transfer exceeds one degree', 0.23825418490142972) |
| drum | Duplicate source payload; requires sense/variant review |
| dumb | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.26229568089477) |
| east | Duplicate source payload; requires sense/variant review |
| egg | Duplicate source payload; requires sense/variant review |
| emotion | Duplicate source payload; requires sense/variant review |
| energy | Duplicate source payload; requires sense/variant review |
| english | Duplicate source payload; requires sense/variant review |
| enjoy | Duplicate source payload; requires sense/variant review |
| eraser | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 177.21188670684285) |
| escape | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.19045653463664) |
| evaluate | Duplicate source payload; requires sense/variant review |
| example | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 172.81155497353535) |
| excuse | Duplicate source payload; requires sense/variant review |
| explode | Duplicate source payload; requires sense/variant review |
| express | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.33471391787413) |
| eyes | Duplicate source payload; requires sense/variant review |
| face | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 178.13179398495492) |
| farm | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.51035327059347) |
| fat | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.14989211448804) |
| fault | Duplicate source payload; requires sense/variant review |
| first | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 171.29179720024405) |
| fix | Duplicate source payload; requires sense/variant review |
| flag | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.35334808674648) |
| fool | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.56973365177637) |
| football | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.93368969085282) |
| forever | Duplicate source payload; requires sense/variant review |
| freeway | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.58245384383218) |
| freeze | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 177.85279815910278) |
| front | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.81219857772209) |
| fun | ('Bone direction transfer exceeds one degree', 0.02229757384280691) |
| game | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.81615890589313) |
| garage | Duplicate source payload; requires sense/variant review |
| gift | ('Bone direction transfer exceeds one degree', 0.06716921320588731) |
| glasses | Duplicate source payload; requires sense/variant review |
| gold | Duplicate source payload; requires sense/variant review |
| gomer | Duplicate source payload; requires sense/variant review |
| graduate | Duplicate source payload; requires sense/variant review |
| grammar | Duplicate source payload; requires sense/variant review |
| guilty | Duplicate source payload; requires sense/variant review |
| guitar | Duplicate source payload; requires sense/variant review |
| half | Duplicate source payload; requires sense/variant review |
| heap | Duplicate source payload; requires sense/variant review |
| heart | Duplicate source payload; requires sense/variant review |
| helicopter | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.9338057032819) |
| high | Duplicate source payload; requires sense/variant review |
| hop | Duplicate source payload; requires sense/variant review |
| independent | Duplicate source payload; requires sense/variant review |
| inspire | Duplicate source payload; requires sense/variant review |
| interest | Duplicate source payload; requires sense/variant review |
| interpreter | Duplicate source payload; requires sense/variant review |
| island | Duplicate source payload; requires sense/variant review |
| israel | Duplicate source payload; requires sense/variant review |
| jacket | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.39529535744964) |
| jewelry | Duplicate source payload; requires sense/variant review |
| judge | Duplicate source payload; requires sense/variant review |
| kill | Duplicate source payload; requires sense/variant review |
| king | Duplicate source payload; requires sense/variant review |
| land | Duplicate source payload; requires sense/variant review |
| language | Duplicate source payload; requires sense/variant review |
| last | Duplicate source payload; requires sense/variant review |
| later | Duplicate source payload; requires sense/variant review |
| laugh | Duplicate source payload; requires sense/variant review |
| lead | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.5172287957434) |
| lemon | Duplicate source payload; requires sense/variant review |
| lesson | Duplicate source payload; requires sense/variant review |
| line | Duplicate source payload; requires sense/variant review |
| lion | Invalid interior source bone lengths |
| list | Duplicate source payload; requires sense/variant review |
| lose | Duplicate source payload; requires sense/variant review |
| loud | ('Bone direction transfer exceeds one degree', 0.055404879952371346) |
| machine | Duplicate source payload; requires sense/variant review |
| magic | ('Bone direction transfer exceeds one degree', 0.046044746162929334) |
| manage | Duplicate source payload; requires sense/variant review |
| match | Duplicate source payload; requires sense/variant review |
| measure | Duplicate source payload; requires sense/variant review |
| medicine | Duplicate source payload; requires sense/variant review |
| middle | Duplicate source payload; requires sense/variant review |
| mind | Duplicate source payload; requires sense/variant review |
| monday | Duplicate source payload; requires sense/variant review |
| mountain | ('Bone direction transfer exceeds one degree', 0.044449709279380425) |
| museum | Duplicate source payload; requires sense/variant review |
| mustache | Duplicate source payload; requires sense/variant review |
| myself | Duplicate source payload; requires sense/variant review |
| near | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 171.37746683400763) |
| neutral | Duplicate source payload; requires sense/variant review |
| night | Invalid interior source bone lengths |
| one | Duplicate source payload; requires sense/variant review |
| onion | Invalid interior source bone lengths |
| oral | Duplicate source payload; requires sense/variant review |
| out | ('Bone direction transfer exceeds one degree', 0.13857098321656955) |
| owe | Duplicate source payload; requires sense/variant review |
| pants | Duplicate source payload; requires sense/variant review |
| peace | Duplicate source payload; requires sense/variant review |
| peach | Duplicate source payload; requires sense/variant review |
| pencil | Duplicate source payload; requires sense/variant review |
| pig | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.23292915322213) |
| policeman | Duplicate source payload; requires sense/variant review |
| poor | Duplicate source payload; requires sense/variant review |
| popcorn | Duplicate source payload; requires sense/variant review |
| positive | Duplicate source payload; requires sense/variant review |
| possible | Duplicate source payload; requires sense/variant review |
| pour | Duplicate source payload; requires sense/variant review |
| predict | Duplicate source payload; requires sense/variant review |
| priest | Duplicate source payload; requires sense/variant review |
| prison | Duplicate source payload; requires sense/variant review |
| process | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.11547404107083) |
| program | Duplicate source payload; requires sense/variant review |
| promise | ('Bone direction transfer exceeds one degree', 0.019513914389661956) |
| proof | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 173.45794794779584) |
| pumpkin | Duplicate source payload; requires sense/variant review |
| quit | Duplicate source payload; requires sense/variant review |
| rabbit | ('Bone direction transfer exceeds one degree', 0.051810565410271445) |
| rainbow | Duplicate source payload; requires sense/variant review |
| rat | Duplicate source payload; requires sense/variant review |
| reason | Duplicate source payload; requires sense/variant review |
| relief | Duplicate source payload; requires sense/variant review |
| religion | Duplicate source payload; requires sense/variant review |
| remember | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 177.0629926097791) |
| remove | Duplicate source payload; requires sense/variant review |
| resist | Duplicate source payload; requires sense/variant review |
| respect | Duplicate source payload; requires sense/variant review |
| rest | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.93239506636976) |
| ring | Duplicate source payload; requires sense/variant review |
| river | Duplicate source payload; requires sense/variant review |
| rooster | Duplicate source payload; requires sense/variant review |
| rope | Duplicate source payload; requires sense/variant review |
| rule | Duplicate source payload; requires sense/variant review |
| salt | Duplicate source payload; requires sense/variant review |
| saturday | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 177.23469179546296) |
| science | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.62435931035444) |
| scientist | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.59166382311076) |
| scissors | Duplicate source payload; requires sense/variant review |
| secret | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.97863856371782) |
| sequence | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.28999954309552) |
| shame | ('Bone direction transfer exceeds one degree', 0.019197962606869845) |
| shampoo | Duplicate source payload; requires sense/variant review |
| shape | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.54845097679421) |
| shave | Invalid interior source bone lengths |
| shoulder | Duplicate source payload; requires sense/variant review |
| shower | ('Bone direction transfer exceeds one degree', 0.021353529008263945) |
| shrimp | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 169.89900713806898) |
| situation | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 178.17321525923606) |
| skate | Duplicate source payload; requires sense/variant review |
| ski | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 164.56420630802816) |
| smoking | Duplicate source payload; requires sense/variant review |
| snob | Duplicate source payload; requires sense/variant review |
| socks | 'animations' |
| soda | ('Bone direction transfer exceeds one degree', 0.02144253895845266) |
| south | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 176.17900645892945) |
| specific | Duplicate source payload; requires sense/variant review |
| star | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 172.9893858617399) |
| sticky | Duplicate source payload; requires sense/variant review |
| strawberry | Duplicate source payload; requires sense/variant review |
| strict | Duplicate source payload; requires sense/variant review |
| subtract | Invalid interior source bone lengths |
| sun | Duplicate source payload; requires sense/variant review |
| suspend | Invalid interior source bone lengths |
| sweep | ('Bone direction transfer exceeds one degree', 0.09637242611301339) |
| swim | Duplicate source payload; requires sense/variant review |
| talk | Duplicate source payload; requires sense/variant review |
| taste | Duplicate source payload; requires sense/variant review |
| team | Duplicate source payload; requires sense/variant review |
| tease | Duplicate source payload; requires sense/variant review |
| technology | Invalid interior source bone lengths |
| teeth | ('Bone direction transfer exceeds one degree', 0.0560475528562821) |
| thanksgiving | Duplicate source payload; requires sense/variant review |
| that | ('Bone direction transfer exceeds one degree', 0.04570107946370582) |
| there | Duplicate source payload; requires sense/variant review |
| ticket | ('Bone direction transfer exceeds one degree', 0.06457488058656122) |
| toast | ('Bone direction transfer exceeds one degree', 0.09553134090864177) |
| toothbrush | Duplicate source payload; requires sense/variant review |
| tough | Duplicate source payload; requires sense/variant review |
| translate | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 172.95972731121284) |
| travel | Duplicate source payload; requires sense/variant review |
| tree | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 174.94643453092849) |
| turkey | Duplicate source payload; requires sense/variant review |
| type | Duplicate source payload; requires sense/variant review |
| vacation | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 177.20829232286818) |
| vegetable | Duplicate source payload; requires sense/variant review |
| vomit | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.58052011043168) |
| war | Duplicate source payload; requires sense/variant review |
| warm | Duplicate source payload; requires sense/variant review |
| wedding | ('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame', 175.49584693471934) |
| west | Duplicate source payload; requires sense/variant review |
| whale | Duplicate source payload; requires sense/variant review |
| whistle | Duplicate source payload; requires sense/variant review |
| white | Duplicate source payload; requires sense/variant review |
| win | Invalid interior source bone lengths |
| wish | Duplicate source payload; requires sense/variant review |
| word | Duplicate source payload; requires sense/variant review |
| worm | Duplicate source payload; requires sense/variant review |
| wristwatch | Duplicate source payload; requires sense/variant review |

## Machine-readable inventory and limitations

`COMBINED_NEW_VOCABULARY.csv` includes all 743 active entries, not just the 511 additions: source, ID, every English form, actual action, asset path, lexical/fallback distinction, test evidence, missing-action status and ASL review status. CSV uses UTF-8 BOM for Excel.

All entries remain unreviewed previews. Actual GLB motions do not themselves prove lexical meaning, qualified linguistic review or complete ASL grammar. Fine finger, wrist, torso contact and non-manual evaluation remain incomplete. The shoulder report must be read separately when available.
