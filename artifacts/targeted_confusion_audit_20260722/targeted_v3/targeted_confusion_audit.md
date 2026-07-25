# Targeted Confusion Audit

Model: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3\best.keras`
Features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
FPS stress features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236_fps`

## Headline
### test
- `mean`: n=2620 top1=0.627 top3=0.825 top5=0.880
- `last`: n=2620 top1=0.587 top3=0.797 top5=0.865
- `early4`: n=2620 top1=0.083 top3=0.132 top5=0.154
- `early6`: n=2620 top1=0.139 top3=0.241 top5=0.297

### fps_val
- `mean`: n=3264 top1=0.658 top3=0.839 top5=0.885
- `last`: n=3264 top1=0.608 top3=0.804 top5=0.869
- `early4`: n=3264 top1=0.331 top3=0.502 top5=0.571
- `early6`: n=3264 top1=0.438 top3=0.628 top5=0.695

## Per-Class Held-Out Test
### View: mean
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 0.87 | 1.00 | 1.7 | IMPORTANT:10, FAMILY:3, HOUSE:1, CLOSE:1 |
| FAMILY | 12 | 0.83 | 0.92 | 1.00 | 1.4 | FAMILY:10, MANY:1, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.67 | 0.75 | 0.75 | 3.1 | INTRODUCE:8, WHOLE:1, HOUSE:1, WITH:1, CLOTHES:1 |
| SELL | 11 | 0.64 | 0.91 | 1.00 | 1.7 | SELL:7, STRONG:2, SHOP1:2 |
| PUT | 11 | 0.73 | 0.91 | 0.91 | 1.9 | PUT:8, MOVE:2, SLOW:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 1.00 | 1.3 | DECIDE1:12, CANNOT:1, STREET:1 |
| SHOP1 | 10 | 0.30 | 0.80 | 0.90 | 2.5 | SELL:5, SHOP1:3, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.64 | 0.91 | 1.00 | 1.7 | WANT2:7, WAIT:2, AGAIN:1, TOOMUCH:1 |
| MANY | 11 | 0.73 | 1.00 | 1.00 | 1.5 | MANY:8, WANT2:2, CAR:1 |
| WAIT | 11 | 0.45 | 0.82 | 0.91 | 3.4 | WAIT:5, SAD:4, WANT2:1, RIGHT3:1 |
| MEET | 9 | 0.78 | 0.89 | 1.00 | 1.6 | MEET:7, GIFT:1, DOWNLOAD:1 |
| KNOW | 13 | 0.46 | 0.77 | 1.00 | 2.2 | KNOW:6, LUNCH1:3, WHY:2, SEEM:1, SICK:1 |
| HELLO | 10 | 0.60 | 0.80 | 0.90 | 2.4 | HELLO:6, FATHER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.8 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 0.92 | 1.00 | 1.2 | WE:11, GIVE:1 |
| LIVE2 | 12 | 0.75 | 0.83 | 0.92 | 2.1 | LIVE2:9, BABY1:1, TIRED:1, WHICH:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: last
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 0.80 | 0.87 | 4.6 | IMPORTANT:10, FAMILY:3, WHY:1, TEACH2:1 |
| FAMILY | 12 | 0.83 | 0.92 | 1.00 | 1.4 | FAMILY:10, MANY:1, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.50 | 0.75 | 1.00 | 2.2 | INTRODUCE:6, WHOLE:2, YOUNG:1, HAVE:1, HOW1:1, CLOTHES:1 |
| SELL | 11 | 0.55 | 0.82 | 0.91 | 2.1 | SELL:6, SHOP1:3, STRONG:2 |
| PUT | 11 | 0.55 | 0.73 | 0.82 | 5.6 | PUT:6, MOVE:2, TEACH2:1, CAKE:1, JUMP:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 0.93 | 1.5 | DECIDE1:12, MEET:1, ROAD:1 |
| SHOP1 | 10 | 0.20 | 0.70 | 0.90 | 3.5 | SELL:6, SHOP1:2, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.73 | 0.91 | 0.91 | 1.8 | WANT2:8, STREET:1, WAIT:1, TOOMUCH:1 |
| MANY | 11 | 0.64 | 0.82 | 0.91 | 2.2 | MANY:7, WANT2:2, CAR:1, NOW:1 |
| WAIT | 11 | 0.36 | 0.82 | 0.91 | 2.9 | WAIT:4, SAD:3, WANT2:2, EASY:1, NEW:1 |
| MEET | 9 | 0.89 | 0.89 | 1.00 | 1.3 | MEET:8, GIFT:1 |
| KNOW | 13 | 0.54 | 0.92 | 0.92 | 2.8 | KNOW:7, LUNCH1:4, WHY:2 |
| HELLO | 10 | 0.40 | 0.70 | 0.80 | 3.1 | HELLO:4, FATHER:2, NEVER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.6 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 1.00 | 1.00 | 1.1 | WE:11, GIVE:1 |
| LIVE2 | 12 | 0.67 | 0.75 | 0.92 | 2.1 | LIVE2:8, BABY1:1, TIRED:1, WHILE:1, TRY:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: early4
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.07 | 0.20 | 0.20 | 69.1 | WANT2:2, SELL:2, EAT1:1, COUNTRY:1, DECIDE1:1, USE:1, IMPORTANT:1, FAMILY:1 |
| FAMILY | 12 | 0.00 | 0.08 | 0.42 | 42.8 | TEACHER:2, MOUTH:1, MEET:1, SORRY:1, NOW:1, HOUSE:1, BREAKFAST1:1, SELL:1 |
| MORE | 11 | 0.00 | 0.00 | 0.00 | 93.4 | WHAT1:2, SELL:1, WANT2:1, BOTH:1, LUNCH1:1, SPECIAL1:1, SURE:1, GIVE:1 |
| INTRODUCE | 12 | 0.00 | 0.00 | 0.08 | 69.7 | TABLE:2, SELL:2, WANT2:2, OPEN:1, NOW:1, BOTH:1, COUNTRY:1, EASY:1 |
| SELL | 11 | 0.27 | 0.36 | 0.36 | 65.5 | SELL:3, DRINK2:1, MEET:1, BUY:1, MEAT1:1, HOUSE:1, LOVE:1, HELLO:1 |
| PUT | 11 | 0.09 | 0.09 | 0.18 | 68.8 | YOU:1, TOOMUCH:1, HURRY:1, COUNTRY:1, YESTERDAY:1, THEN:1, SLOW:1, PUT:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.36 | 73.6 | DECIDE1:3, HELLO:2, SELL:2, LUNCH1:1, FAST:1, MOST:1, ONE:1, MUCH:1 |
| SHOP1 | 10 | 0.30 | 0.30 | 0.40 | 80.2 | SHOP1:3, HOSPITAL1:1, YEAR:1, WHAT1:1, MORE:1, PUT:1, COUNTRY:1, TOUCH:1 |
| TEACH2 | 11 | 0.36 | 0.36 | 0.36 | 41.1 | TEACH2:4, HELLO:2, TOUCH:1, KNOW:1, COUNTRY:1, TODAY:1, WINDOW:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.27 | 54.3 | KNOW:3, WANT2:3, GIVE:1, SMALL:1, SLOW:1, BUY:1, SELL:1 |
| MANY | 11 | 0.09 | 0.09 | 0.18 | 52.6 | COUNTRY:2, EAT1:1, TOOMUCH:1, HOSPITAL1:1, BOTH:1, LETTER2:1, HOW1:1, TOUCH:1 |
| WAIT | 11 | 0.27 | 0.27 | 0.27 | 93.1 | WAIT:3, PICK:1, USE:1, NOW:1, EAT1:1, COUNTRY:1, SISTER:1, HAPPY:1 |
| MEET | 9 | 0.00 | 0.00 | 0.00 | 85.7 | SELL:2, SORRY:1, COUNTRY:1, NOW:1, WHAT1:1, CANNOT:1, MOUTH:1, EAT1:1 |
| KNOW | 13 | 0.08 | 0.23 | 0.23 | 35.3 | EAT1:2, HOW1:1, GIVE:1, HOME:1, COUNTRY:1, SELL:1, KNOW:1, ALWAYS:1 |
| HELLO | 10 | 0.10 | 0.30 | 0.30 | 34.4 | SURE:1, BYE:1, YEAR:1, MAN:1, YOUR:1, THINK:1, TIME:1, SIT:1 |
| DONTKNOW | 10 | 0.10 | 0.10 | 0.10 | 53.7 | TEACHER:1, HOW1:1, WHAT1:1, WANT2:1, TOUCH:1, YEAR:1, SURE:1, DONTKNOW:1 |
| WE | 12 | 0.08 | 0.17 | 0.17 | 109.2 | KNOW:2, RUN2:1, ALWAYS:1, LUNCH1:1, WE:1, PICK:1, BOTH:1, PAY:1 |
| LIVE2 | 12 | 0.00 | 0.08 | 0.08 | 140.9 | WANT2:2, HELLO:1, TABLE:1, WHILE:1, TOUCH:1, EAT1:1, BOTH:1, KNOW:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 82.6 | HELLO:2, CANNOT:1, KNOW:1, STRONG:1, HOT:1, GIVE:1, YOU:1, SURE:1 |

### View: early6
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.13 | 0.27 | 0.40 | 38.8 | COUNT:2, IMPORTANT:2, WITH:1, SAME2:1, WANT2:1, FREE:1, SLOW:1, HOUSE:1 |
| FAMILY | 12 | 0.17 | 0.17 | 0.42 | 34.6 | FAMILY:2, MANY:1, KNOW:1, WANT2:1, TEACHER:1, WAIT:1, HOUSE:1, BED2:1 |
| MORE | 11 | 0.00 | 0.09 | 0.18 | 46.0 | PARTY1:1, ON:1, SMALL:1, HARD:1, SPECIAL1:1, FAMILY:1, WRITE:1, HERE:1 |
| INTRODUCE | 12 | 0.00 | 0.25 | 0.25 | 28.5 | PUT:2, SELL:2, WANT2:2, COLD:1, NOW:1, SMALL:1, FREE:1, NEW:1 |
| SELL | 11 | 0.45 | 0.82 | 0.82 | 12.9 | SELL:5, CAR:1, AGAIN:1, KNOW:1, SHOP1:1, JUMP:1, SURE:1 |
| PUT | 11 | 0.18 | 0.18 | 0.27 | 31.5 | PUT:2, USE:1, BUY:1, SMALL:1, COUNTRY:1, ON:1, SLOW:1, TOOMUCH:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.29 | 29.6 | DECIDE1:3, LUNCH1:1, WANT2:1, RUN2:1, MAN:1, SELL:1, HAVE:1, SEE:1 |
| SHOP1 | 10 | 0.20 | 0.40 | 0.40 | 59.2 | SELL:3, SHOP1:2, HOSPITAL1:1, YEAR:1, WHAT1:1, TEACH2:1, PICK:1 |
| TEACH2 | 11 | 0.45 | 0.45 | 0.55 | 21.6 | TEACH2:5, SELL:2, TOOMUCH:1, YEAR:1, TEACHER:1, CLOTHES:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.36 | 52.5 | WANT2:3, SELL:2, LETTER2:1, NOW:1, CAR:1, HAVE:1, BUY:1, EAT1:1 |
| MANY | 11 | 0.18 | 0.27 | 0.36 | 42.4 | MANY:2, LOVE:1, WHAT1:1, HOSPITAL1:1, SELL:1, SHOP1:1, ONE:1, CAKE:1 |
| WAIT | 11 | 0.18 | 0.36 | 0.36 | 85.6 | WAIT:2, SORRY:1, YES:1, WANT2:1, WITH:1, MORE:1, SISTER:1, GOOD:1 |
| MEET | 9 | 0.22 | 0.56 | 0.56 | 46.8 | MEET:2, TO:2, WHILE:1, YEAR:1, HURRY:1, SURE:1, ALWAYS:1 |
| KNOW | 13 | 0.38 | 0.46 | 0.54 | 27.6 | KNOW:5, HELLO:2, LUNCH1:2, ANY:1, WHY:1, BREAKFAST1:1, WHAT1:1 |
| HELLO | 10 | 0.20 | 0.40 | 0.70 | 44.4 | BYE:2, HELLO:2, SEEM:1, YEAR:1, FATHER:1, BREAKFAST1:1, HOSPITAL1:1, NEED:1 |
| DONTKNOW | 10 | 0.00 | 0.20 | 0.30 | 48.5 | TEACHER:2, LUNCH1:1, WANT2:1, CLOSE:1, SELL:1, BREAKFAST1:1, HELLO:1, ENOUGH:1 |
| WE | 12 | 0.08 | 0.42 | 0.42 | 69.9 | CANNOT:2, HEAR1:1, HARD:1, WALK2:1, SURE:1, HURRY:1, PAY:1, WE:1 |
| LIVE2 | 12 | 0.25 | 0.33 | 0.33 | 85.2 | LIVE2:3, MEAT1:2, TOOMUCH:1, BABY1:1, LUNCH1:1, TIRED:1, WANT2:1, SORRY:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.18 | 67.0 | SELL:3, HERE:1, RUN2:1, STRONG:1, GIVE:1, YOU:1, SURE:1, BOOK:1 |

## Group Matrices - Held-Out Test Last View
### important_family_more_introduce (top1=0.74, n=50)
| true / pred | IMPORTANT | FAMILY | MORE | INTRODUCE |
|---|---:|---:|---:|---:|
| IMPORTANT | 10 | 3 | 0 | 0 |
| FAMILY | 0 | 10 | 0 | 0 |
| MORE | 0 | 0 | 11 | 0 |
| INTRODUCE | 0 | 0 | 0 | 6 |

### sell_put_decide_shop_teach (top1=0.63, n=57)
| true / pred | SELL | PUT | DECIDE1 | SHOP1 | TEACH2 |
|---|---:|---:|---:|---:|---:|
| SELL | 6 | 0 | 0 | 3 | 0 |
| PUT | 0 | 6 | 0 | 0 | 1 |
| DECIDE1 | 0 | 0 | 12 | 0 | 0 |
| SHOP1 | 6 | 0 | 0 | 2 | 1 |
| TEACH2 | 0 | 0 | 0 | 0 | 10 |

### want_many_wait_meet (top1=0.64, n=42)
| true / pred | WANT2 | MANY | WAIT | MEET |
|---|---:|---:|---:|---:|
| WANT2 | 8 | 0 | 1 | 0 |
| MANY | 2 | 7 | 0 | 0 |
| WAIT | 2 | 0 | 4 | 0 |
| MEET | 0 | 0 | 0 | 8 |

### know_hello_sell_dontknow (top1=0.59, n=44)
| true / pred | KNOW | HELLO | SELL | DONTKNOW |
|---|---:|---:|---:|---:|
| KNOW | 7 | 0 | 0 | 0 |
| HELLO | 0 | 4 | 0 | 0 |
| SELL | 0 | 0 | 6 | 0 |
| DONTKNOW | 0 | 0 | 0 | 9 |

### we_live_strong_sell (top1=0.74, n=46)
| true / pred | WE | LIVE2 | STRONG | SELL |
|---|---:|---:|---:|---:|
| WE | 11 | 0 | 0 | 0 |
| LIVE2 | 0 | 8 | 0 | 0 |
| STRONG | 0 | 0 | 9 | 0 |
| SELL | 0 | 0 | 2 | 6 |
