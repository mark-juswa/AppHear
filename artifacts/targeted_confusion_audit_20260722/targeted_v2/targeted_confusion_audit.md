# Targeted Confusion Audit

Model: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2\best.keras`
Features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
FPS stress features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236_fps`

## Headline
### test
- `mean`: n=2620 top1=0.623 top3=0.819 top5=0.879
- `last`: n=2620 top1=0.583 top3=0.794 top5=0.858
- `early4`: n=2620 top1=0.081 top3=0.130 top5=0.158
- `early6`: n=2620 top1=0.139 top3=0.240 top5=0.298

### fps_val
- `mean`: n=3264 top1=0.659 top3=0.839 top5=0.886
- `last`: n=3264 top1=0.598 top3=0.807 top5=0.864
- `early4`: n=3264 top1=0.338 top3=0.504 top5=0.568
- `early6`: n=3264 top1=0.435 top3=0.624 top5=0.693

## Per-Class Held-Out Test
### View: mean
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.60 | 0.80 | 1.00 | 1.9 | IMPORTANT:9, FAMILY:4, HOUSE:1, COMPUTER:1 |
| FAMILY | 12 | 0.83 | 0.92 | 1.00 | 1.4 | FAMILY:10, MANY:1, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.58 | 0.75 | 0.83 | 2.5 | INTRODUCE:7, HOUSE:2, NEW:1, WHOLE:1, WITH:1 |
| SELL | 11 | 0.55 | 0.82 | 1.00 | 2.1 | SELL:6, SHOP1:3, STRONG:2 |
| PUT | 11 | 0.91 | 0.91 | 0.91 | 1.5 | PUT:10, SLOW:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 1.00 | 1.3 | DECIDE1:12, CANNOT:1, STREET:1 |
| SHOP1 | 10 | 0.40 | 1.00 | 1.00 | 1.7 | SHOP1:4, SELL:4, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.64 | 0.82 | 1.00 | 1.9 | WANT2:7, WAIT:2, AGAIN:1, TOOMUCH:1 |
| MANY | 11 | 0.73 | 0.91 | 1.00 | 1.5 | MANY:8, CAR:1, WAIT:1, WANT2:1 |
| WAIT | 11 | 0.36 | 0.82 | 0.91 | 3.2 | WAIT:4, SAD:4, WANT2:1, RIGHT3:1, NEW:1 |
| MEET | 9 | 0.78 | 0.89 | 0.89 | 1.7 | MEET:7, GIFT:1, DOWNLOAD:1 |
| KNOW | 13 | 0.54 | 0.85 | 1.00 | 1.9 | KNOW:7, LUNCH1:2, WHY:2, SEEM:1, SICK:1 |
| HELLO | 10 | 0.40 | 0.80 | 0.90 | 2.7 | HELLO:4, SEEM:2, FATHER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.6 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 0.92 | 1.00 | 1.3 | WE:11, GIVE:1 |
| LIVE2 | 12 | 0.75 | 0.83 | 0.92 | 2.2 | LIVE2:9, BABY1:1, TIRED:1, WHICH:1 |
| STRONG | 11 | 0.73 | 1.00 | 1.00 | 1.3 | STRONG:8, DRIVE:1, COLD:1, CAR:1 |

### View: last
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 0.80 | 0.87 | 4.9 | IMPORTANT:10, FAMILY:3, WHY:1, TEACH2:1 |
| FAMILY | 12 | 0.75 | 0.92 | 0.92 | 1.7 | FAMILY:9, MANY:1, HOUSE:1, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.67 | 0.75 | 1.00 | 1.9 | INTRODUCE:8, WHOLE:1, HAVE:1, HOW1:1, CLOTHES:1 |
| SELL | 11 | 0.45 | 0.73 | 0.82 | 2.5 | SELL:5, SHOP1:3, STRONG:3 |
| PUT | 11 | 0.55 | 0.82 | 0.82 | 4.7 | PUT:6, MOVE:2, NIGHT1:2, TEACH2:1 |
| DECIDE1 | 14 | 0.79 | 0.93 | 0.93 | 1.5 | DECIDE1:11, MEET:1, IMPORTANT:1, STREET:1 |
| SHOP1 | 10 | 0.50 | 0.70 | 0.80 | 3.9 | SHOP1:5, SELL:2, INTRODUCE:1, TEACH2:1, PARTY1:1 |
| TEACH2 | 11 | 1.00 | 1.00 | 1.00 | 1.0 | TEACH2:11 |
| WANT2 | 11 | 0.55 | 0.91 | 0.91 | 2.2 | WANT2:6, STREET:2, WAIT:2, HERE:1 |
| MANY | 11 | 0.64 | 0.82 | 0.82 | 2.7 | MANY:7, WANT2:2, CAR:1, NOW:1 |
| WAIT | 11 | 0.36 | 0.82 | 0.91 | 3.1 | WAIT:4, SAD:3, WANT2:1, RIGHT3:1, EASY:1, NEW:1 |
| MEET | 9 | 0.89 | 0.89 | 1.00 | 1.3 | MEET:8, GIFT:1 |
| KNOW | 13 | 0.54 | 0.92 | 0.92 | 2.7 | KNOW:7, LUNCH1:4, WHY:2 |
| HELLO | 10 | 0.30 | 0.80 | 0.80 | 3.3 | HELLO:3, FATHER:2, HUSBAND:1, BYE:1, MAN:1, NEVER:1, HOSPITAL1:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.5 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 1.00 | 1.00 | 1.2 | WE:11, GIVE:1 |
| LIVE2 | 12 | 0.67 | 0.83 | 0.83 | 2.4 | LIVE2:8, BABY1:1, TIRED:1, WHILE:1, TRY:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: early4
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.13 | 0.33 | 0.40 | 56.5 | TODAY:2, IMPORTANT:2, EAT1:1, COUNTRY:1, COUNT:1, FREE:1, USE:1, FAMILY:1 |
| FAMILY | 12 | 0.08 | 0.17 | 0.33 | 45.0 | TEACHER:2, CANNOT:1, MEET:1, FAMILY:1, HOW1:1, HOUSE:1, BREAKFAST1:1, SELL:1 |
| MORE | 11 | 0.00 | 0.00 | 0.00 | 78.9 | HAVE:1, WANT2:1, TODAY:1, COUNTRY:1, SPECIAL1:1, MANY:1, SLOW:1, SURE:1 |
| INTRODUCE | 12 | 0.00 | 0.00 | 0.08 | 58.5 | SELL:2, WANT2:2, OPEN:1, HAVE:1, TABLE:1, TODAY:1, AT:1, COUNTRY:1 |
| SELL | 11 | 0.18 | 0.27 | 0.36 | 64.7 | STILL:2, MEET:2, SELL:2, IMPORTANT:1, STRONG:1, HOUSE:1, LOVE:1, HELLO:1 |
| PUT | 11 | 0.18 | 0.18 | 0.18 | 42.3 | PUT:2, IMPORTANT:2, SHOP1:1, COUNTRY:1, YESTERDAY:1, SMALL:1, SLOW:1, NIGHT1:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.36 | 76.4 | DECIDE1:3, HELLO:2, LUNCH1:1, FAST:1, MOST:1, BED2:1, NIGHT1:1, SELL:1 |
| SHOP1 | 10 | 0.30 | 0.30 | 0.40 | 49.6 | SHOP1:3, HOSPITAL1:1, IMPORTANT:1, WHAT1:1, MORE:1, PUT:1, COUNTRY:1, TOUCH:1 |
| TEACH2 | 11 | 0.36 | 0.36 | 0.36 | 31.8 | TEACH2:4, HELLO:2, TOUCH:1, KNOW:1, COUNTRY:1, TODAY:1, NIGHT1:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.27 | 64.7 | WANT2:3, PUT:2, KNOW:1, GIVE:1, SMALL:1, SLOW:1, BUY:1, SELL:1 |
| MANY | 11 | 0.09 | 0.18 | 0.18 | 24.9 | EAT1:1, PUT:1, HOSPITAL1:1, MOVIE1:1, HOUR:1, LETTER2:1, HOW1:1, TOUCH:1 |
| WAIT | 11 | 0.27 | 0.27 | 0.27 | 74.5 | WAIT:3, PICK:1, MORE:1, TOUCH:1, EAT1:1, COUNTRY:1, SISTER:1, HAPPY:1 |
| MEET | 9 | 0.00 | 0.00 | 0.00 | 83.8 | WANT2:1, COUNTRY:1, NOW:1, WHAT1:1, NEED:1, CANNOT:1, SELL:1, HOME:1 |
| KNOW | 13 | 0.08 | 0.15 | 0.23 | 43.0 | EAT1:2, TODAY:1, GIVE:1, HOME:1, COUNTRY:1, SMALL:1, KNOW:1, YESTERDAY:1 |
| HELLO | 10 | 0.10 | 0.20 | 0.30 | 39.2 | SURE:1, BYE:1, IMPORTANT:1, MAN:1, YOUR:1, THINK:1, TIME:1, SIT:1 |
| DONTKNOW | 10 | 0.10 | 0.10 | 0.10 | 59.1 | TEACHER:1, HOW1:1, WHAT1:1, NEED:1, TOUCH:1, YEAR:1, SURE:1, DONTKNOW:1 |
| WE | 12 | 0.08 | 0.17 | 0.17 | 121.8 | KNOW:2, IMPORTANT:1, ALWAYS:1, LUNCH1:1, WE:1, PICK:1, PUT:1, PAY:1 |
| LIVE2 | 12 | 0.00 | 0.08 | 0.08 | 144.0 | MEET:1, TABLE:1, WHILE:1, TOUCH:1, EAT1:1, MORE:1, KNOW:1, NICE:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 78.0 | HELLO:2, MORE:1, KNOW:1, STRONG:1, SHOP1:1, GIVE:1, YOU:1, SURE:1 |

### View: early6
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.13 | 0.27 | 0.47 | 33.9 | COUNT:2, IMPORTANT:2, WITH:1, SAME2:1, WANT2:1, FREE:1, SLOW:1, HOUSE:1 |
| FAMILY | 12 | 0.17 | 0.17 | 0.25 | 34.2 | FAMILY:2, MANY:1, KNOW:1, WANT2:1, TEACHER:1, WAIT:1, HOUSE:1, BED2:1 |
| MORE | 11 | 0.09 | 0.09 | 0.18 | 41.8 | PUT:1, ON:1, SMALL:1, BREAKFAST1:1, OPEN:1, MORE:1, WRITE:1, HERE:1 |
| INTRODUCE | 12 | 0.00 | 0.25 | 0.25 | 24.5 | SELL:3, PUT:2, WANT2:2, COLD:1, SMALL:1, TODAY:1, NEW:1, HAVE:1 |
| SELL | 11 | 0.36 | 0.73 | 0.82 | 12.0 | SELL:4, KNOW:2, STILL:1, AGAIN:1, SHOP1:1, DOOR:1, SURE:1 |
| PUT | 11 | 0.18 | 0.36 | 0.36 | 20.4 | PUT:2, USE:1, NIGHT1:1, SMALL:1, COUNTRY:1, TOUCH:1, SLOW:1, OPEN:1 |
| DECIDE1 | 14 | 0.29 | 0.29 | 0.29 | 31.2 | DECIDE1:4, LUNCH1:1, FAST:1, RUN2:1, IMPORTANT:1, HAVE:1, SEE:1, STREET:1 |
| SHOP1 | 10 | 0.20 | 0.40 | 0.40 | 39.8 | SHOP1:2, SELL:1, HOSPITAL1:1, YEAR:1, WHAT1:1, TEACH2:1, COUNT:1, TODAY:1 |
| TEACH2 | 11 | 0.45 | 0.45 | 0.55 | 15.3 | TEACH2:5, SELL:2, TODAY:1, YEAR:1, TEACHER:1, CLOTHES:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.27 | 57.3 | WANT2:3, SELL:2, LETTER2:1, NOW:1, CAR:1, IMPORTANT:1, BUY:1, EAT1:1 |
| MANY | 11 | 0.18 | 0.27 | 0.36 | 28.6 | MANY:2, LOVE:1, TOOMUCH:1, HOSPITAL1:1, SELL:1, SHOP1:1, CAKE:1, TODAY:1 |
| WAIT | 11 | 0.18 | 0.36 | 0.36 | 75.3 | WAIT:2, SORRY:1, NIGHT1:1, WANT2:1, WITH:1, MORE:1, SISTER:1, GOOD:1 |
| MEET | 9 | 0.22 | 0.56 | 0.56 | 42.7 | MEET:2, TO:2, WHILE:1, YEAR:1, HURRY:1, SURE:1, HOME:1 |
| KNOW | 13 | 0.38 | 0.46 | 0.54 | 32.8 | KNOW:5, HELLO:2, LUNCH1:1, ANY:1, COUNTRY:1, WHY:1, BREAKFAST1:1, WHAT1:1 |
| HELLO | 10 | 0.20 | 0.40 | 0.60 | 46.1 | BYE:2, HELLO:2, SEEM:1, CLEAN:1, FATHER:1, BREAKFAST1:1, SPECIAL1:1, HUSBAND:1 |
| DONTKNOW | 10 | 0.00 | 0.20 | 0.30 | 50.6 | TEACHER:2, LUNCH1:1, WANT2:1, CLOSE:1, SELL:1, BREAKFAST1:1, HELLO:1, ENOUGH:1 |
| WE | 12 | 0.08 | 0.42 | 0.42 | 73.2 | ALWAYS:2, RUN2:1, HARD:1, WALK2:1, SURE:1, ENTER:1, PAY:1, WE:1 |
| LIVE2 | 12 | 0.25 | 0.33 | 0.33 | 88.0 | LIVE2:3, TOOMUCH:1, BABY1:1, SAME2:1, TIRED:1, MEAT1:1, WANT2:1, NOW:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 68.5 | HERE:1, WELCOME2:1, STRONG:1, SHOP1:1, GIVE:1, WEEK:1, SURE:1, BOOK:1 |

## Group Matrices - Held-Out Test Last View
### important_family_more_introduce (top1=0.76, n=50)
| true / pred | IMPORTANT | FAMILY | MORE | INTRODUCE |
|---|---:|---:|---:|---:|
| IMPORTANT | 10 | 3 | 0 | 0 |
| FAMILY | 0 | 9 | 0 | 0 |
| MORE | 0 | 0 | 11 | 0 |
| INTRODUCE | 0 | 0 | 0 | 8 |

### sell_put_decide_shop_teach (top1=0.67, n=57)
| true / pred | SELL | PUT | DECIDE1 | SHOP1 | TEACH2 |
|---|---:|---:|---:|---:|---:|
| SELL | 5 | 0 | 0 | 3 | 0 |
| PUT | 0 | 6 | 0 | 0 | 1 |
| DECIDE1 | 0 | 0 | 11 | 0 | 0 |
| SHOP1 | 2 | 0 | 0 | 5 | 1 |
| TEACH2 | 0 | 0 | 0 | 0 | 11 |

### want_many_wait_meet (top1=0.60, n=42)
| true / pred | WANT2 | MANY | WAIT | MEET |
|---|---:|---:|---:|---:|
| WANT2 | 6 | 0 | 2 | 0 |
| MANY | 2 | 7 | 0 | 0 |
| WAIT | 1 | 0 | 4 | 0 |
| MEET | 0 | 0 | 0 | 8 |

### know_hello_sell_dontknow (top1=0.55, n=44)
| true / pred | KNOW | HELLO | SELL | DONTKNOW |
|---|---:|---:|---:|---:|
| KNOW | 7 | 0 | 0 | 0 |
| HELLO | 0 | 3 | 0 | 0 |
| SELL | 0 | 0 | 5 | 0 |
| DONTKNOW | 0 | 0 | 0 | 9 |

### we_live_strong_sell (top1=0.72, n=46)
| true / pred | WE | LIVE2 | STRONG | SELL |
|---|---:|---:|---:|---:|
| WE | 11 | 0 | 0 | 0 |
| LIVE2 | 0 | 8 | 0 | 0 |
| STRONG | 0 | 0 | 9 | 0 |
| SELL | 0 | 0 | 3 | 5 |
