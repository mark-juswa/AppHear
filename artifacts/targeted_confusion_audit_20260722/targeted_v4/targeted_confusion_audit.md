# Targeted Confusion Audit

Model: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4\best.keras`
Features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
FPS stress features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236_fps`

## Headline
### test
- `mean`: n=2620 top1=0.621 top3=0.828 top5=0.880
- `last`: n=2620 top1=0.584 top3=0.800 top5=0.861
- `early4`: n=2620 top1=0.080 top3=0.126 top5=0.156
- `early6`: n=2620 top1=0.137 top3=0.235 top5=0.295

### fps_val
- `mean`: n=3264 top1=0.656 top3=0.848 top5=0.888
- `last`: n=3264 top1=0.602 top3=0.802 top5=0.865
- `early4`: n=3264 top1=0.336 top3=0.505 top5=0.569
- `early6`: n=3264 top1=0.438 top3=0.625 top5=0.692

## Per-Class Held-Out Test
### View: mean
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.60 | 0.87 | 1.00 | 1.8 | IMPORTANT:9, FAMILY:4, HOUSE:1, COMPUTER:1 |
| FAMILY | 12 | 0.92 | 0.92 | 1.00 | 1.2 | FAMILY:11, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.67 | 0.83 | 0.83 | 2.2 | INTRODUCE:8, HOUSE:2, YOUNG:1, WHOLE:1 |
| SELL | 11 | 0.64 | 0.91 | 1.00 | 1.8 | SELL:7, STRONG:2, SHOP1:2 |
| PUT | 11 | 0.91 | 0.91 | 0.91 | 1.7 | PUT:10, SLOW:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 1.00 | 1.3 | DECIDE1:12, CANNOT:1, STREET:1 |
| SHOP1 | 10 | 0.40 | 0.90 | 1.00 | 2.0 | SHOP1:4, SELL:4, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.55 | 0.91 | 1.00 | 1.8 | WANT2:6, WAIT:2, HERE:1, AGAIN:1, TOOMUCH:1 |
| MANY | 11 | 0.73 | 0.91 | 1.00 | 1.5 | MANY:8, WANT2:2, CAR:1 |
| WAIT | 11 | 0.36 | 0.82 | 0.91 | 3.9 | WAIT:4, SAD:4, WANT2:1, RIGHT3:1, NEW:1 |
| MEET | 9 | 0.78 | 0.89 | 1.00 | 1.6 | MEET:7, GIFT:1, DOWNLOAD:1 |
| KNOW | 13 | 0.54 | 0.92 | 1.00 | 1.8 | KNOW:7, LUNCH1:3, SEEM:1, WHY:1, SICK:1 |
| HELLO | 10 | 0.60 | 0.80 | 0.90 | 2.2 | HELLO:6, FATHER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.5 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 0.92 | 1.00 | 1.2 | WE:11, US:1 |
| LIVE2 | 12 | 0.75 | 0.83 | 0.92 | 2.0 | LIVE2:9, BABY1:1, TIRED:1, WHICH:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: last
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 0.80 | 0.87 | 5.4 | IMPORTANT:10, FAMILY:3, WHY:1, TEACH2:1 |
| FAMILY | 12 | 0.83 | 0.92 | 1.00 | 1.4 | FAMILY:10, HOUSE:1, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.58 | 0.92 | 1.00 | 1.8 | INTRODUCE:7, YOUNG:1, WHOLE:1, HAVE:1, HOW1:1, CLOTHES:1 |
| SELL | 11 | 0.55 | 0.82 | 0.91 | 2.2 | SELL:6, SHOP1:3, STRONG:2 |
| PUT | 11 | 0.55 | 0.82 | 0.82 | 4.5 | PUT:6, MOVE:2, TEACH2:1, SLOW:1, NIGHT1:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 0.93 | 1.6 | DECIDE1:12, MEET:1, STREET:1 |
| SHOP1 | 10 | 0.40 | 0.60 | 0.80 | 3.8 | SHOP1:4, SELL:4, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.55 | 0.82 | 0.91 | 2.5 | WANT2:6, STREET:2, WAIT:1, HERE:1, TOOMUCH:1 |
| MANY | 11 | 0.55 | 0.82 | 0.82 | 2.7 | MANY:6, CAR:2, WANT2:2, NOW:1 |
| WAIT | 11 | 0.27 | 0.73 | 0.91 | 3.4 | WAIT:3, SAD:3, WANT2:2, EASY:2, NEW:1 |
| MEET | 9 | 0.89 | 0.89 | 1.00 | 1.3 | MEET:8, GIFT:1 |
| KNOW | 13 | 0.62 | 0.92 | 0.92 | 2.6 | KNOW:8, LUNCH1:4, WHY:1 |
| HELLO | 10 | 0.40 | 0.80 | 0.80 | 2.8 | HELLO:4, FATHER:2, NEVER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 1.00 | 1.4 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 1.00 | 1.00 | 1.00 | 1.0 | WE:12 |
| LIVE2 | 12 | 0.67 | 0.83 | 0.92 | 2.2 | LIVE2:8, BABY1:1, TIRED:1, WHILE:1, TRY:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: early4
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.07 | 0.20 | 0.20 | 73.3 | SELL:2, EAT1:1, COUNTRY:1, WANT2:1, NOW:1, FREE:1, USE:1, IMPORTANT:1 |
| FAMILY | 12 | 0.08 | 0.17 | 0.25 | 51.8 | TEACHER:2, CANNOT:1, MEET:1, FAMILY:1, NOW:1, HOUSE:1, BREAKFAST1:1, SELL:1 |
| MORE | 11 | 0.00 | 0.00 | 0.00 | 90.9 | WHAT1:2, SELL:1, WANT2:1, TODAY:1, LUNCH1:1, SPECIAL1:1, SURE:1, GIVE:1 |
| INTRODUCE | 12 | 0.00 | 0.00 | 0.08 | 55.3 | TABLE:2, WANT2:2, OPEN:1, NOW:1, BOTH:1, HELLO:1, SELL:1, COUNTRY:1 |
| SELL | 11 | 0.27 | 0.27 | 0.45 | 62.4 | SELL:3, MEET:2, STAY:1, MEAT1:1, HOUSE:1, LOVE:1, HELLO:1, STILL:1 |
| PUT | 11 | 0.09 | 0.18 | 0.18 | 55.1 | YOU:1, TOOMUCH:1, HURRY:1, COUNTRY:1, YESTERDAY:1, SMALL:1, SLOW:1, PUT:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.36 | 80.2 | DECIDE1:3, HELLO:2, SELL:2, LUNCH1:1, FAST:1, MOST:1, NIGHT1:1, MUCH:1 |
| SHOP1 | 10 | 0.30 | 0.30 | 0.40 | 59.6 | SHOP1:3, HOSPITAL1:1, TICKET:1, WHAT1:1, MORE:1, PUT:1, COUNTRY:1, TOUCH:1 |
| TEACH2 | 11 | 0.36 | 0.36 | 0.36 | 34.5 | TEACH2:4, HELLO:1, BYE:1, SELL:1, KNOW:1, COUNTRY:1, TODAY:1, WINDOW:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.27 | 55.2 | WANT2:3, KNOW:1, GIVE:1, SMALL:1, CHILD:1, SLOW:1, BUY:1, PUT:1 |
| MANY | 11 | 0.09 | 0.09 | 0.09 | 53.8 | FIND:1, TOOMUCH:1, HOSPITAL1:1, MOVIE1:1, HOUR:1, LETTER2:1, HOW1:1, TOUCH:1 |
| WAIT | 11 | 0.27 | 0.27 | 0.27 | 96.1 | WAIT:3, PICK:1, ABOUT2:1, NOW:1, EAT1:1, COUNTRY:1, SISTER:1, HAPPY:1 |
| MEET | 9 | 0.00 | 0.00 | 0.00 | 82.1 | SORRY:1, COUNTRY:1, NOW:1, WHAT1:1, HELLO:1, CANNOT:1, SELL:1, MOUTH:1 |
| KNOW | 13 | 0.08 | 0.08 | 0.23 | 40.2 | TODAY:1, GIVE:1, EAT1:1, HOME:1, COUNTRY:1, SELL:1, KNOW:1, YESTERDAY:1 |
| HELLO | 10 | 0.10 | 0.30 | 0.30 | 35.1 | SURE:1, BYE:1, ABOUT2:1, MAN:1, YOUR:1, THINK:1, HOSPITAL1:1, NICE:1 |
| DONTKNOW | 10 | 0.10 | 0.10 | 0.20 | 49.6 | TEACHER:1, HOW1:1, WANT2:1, HELLO:1, TOUCH:1, YEAR:1, SURE:1, DONTKNOW:1 |
| WE | 12 | 0.00 | 0.17 | 0.17 | 107.9 | KNOW:2, RUN2:1, ALWAYS:1, LUNCH1:1, COUNTRY:1, PICK:1, MOVIE1:1, PAY:1 |
| LIVE2 | 12 | 0.00 | 0.08 | 0.08 | 128.3 | HELLO:2, WANT2:2, TABLE:1, WHILE:1, TOUCH:1, EAT1:1, NOW:1, KNOW:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 75.5 | HELLO:2, CANNOT:1, KNOW:1, STRONG:1, SHOP1:1, GIVE:1, HAPPY:1, SURE:1 |

### View: early6
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.13 | 0.27 | 0.40 | 41.7 | WITH:2, COUNT:2, IMPORTANT:2, WANT2:1, FREE:1, SLOW:1, HOUSE:1, SELL:1 |
| FAMILY | 12 | 0.17 | 0.17 | 0.25 | 38.3 | FAMILY:2, HURRY:2, MANY:1, KNOW:1, WANT2:1, TEACHER:1, WAIT:1, HOUSE:1 |
| MORE | 11 | 0.09 | 0.09 | 0.18 | 42.5 | PARTY1:1, ON:1, SMALL:1, HOSPITAL1:1, SPECIAL1:1, MORE:1, WRITE:1, HERE:1 |
| INTRODUCE | 12 | 0.00 | 0.25 | 0.42 | 22.6 | PUT:2, SELL:2, WANT2:2, COLD:1, NOW:1, SMALL:1, TODAY:1, ROOM:1 |
| SELL | 11 | 0.36 | 0.82 | 0.82 | 11.3 | SELL:4, KNOW:2, PLAY:1, AGAIN:1, SHOP1:1, DOOR:1, SURE:1 |
| PUT | 11 | 0.18 | 0.18 | 0.36 | 24.9 | PUT:2, USE:1, BUY:1, SMALL:1, COUNTRY:1, ON:1, SLOW:1, OPEN:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.29 | 31.1 | DECIDE1:3, LUNCH1:1, FAST:1, RUN2:1, MAN:1, SELL:1, HAVE:1, SEE:1 |
| SHOP1 | 10 | 0.20 | 0.40 | 0.40 | 45.4 | SHOP1:2, SELL:2, HOSPITAL1:1, TICKET:1, WHILE:1, TEACH2:1, PICK:1, HAVE:1 |
| TEACH2 | 11 | 0.45 | 0.45 | 0.55 | 14.5 | TEACH2:5, SELL:2, TOOMUCH:1, COUNTRY:1, TEACHER:1, CLOTHES:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.36 | 52.1 | WANT2:3, SELL:2, HOUR:1, NOW:1, CAR:1, HAVE:1, BUY:1, EAT1:1 |
| MANY | 11 | 0.09 | 0.27 | 0.36 | 44.9 | LOVE:1, HAVE:1, HOSPITAL1:1, SELL:1, MANY:1, SHOP1:1, ONE:1, CAKE:1 |
| WAIT | 11 | 0.18 | 0.36 | 0.36 | 89.7 | WAIT:2, SORRY:1, YES:1, WANT2:1, WITH:1, MORE:1, SISTER:1, GOOD:1 |
| MEET | 9 | 0.22 | 0.56 | 0.56 | 42.6 | MEET:2, TO:2, WHILE:1, COUNTRY:1, HURRY:1, SURE:1, ALWAYS:1 |
| KNOW | 13 | 0.38 | 0.46 | 0.54 | 29.8 | KNOW:5, HELLO:2, LUNCH1:2, ANY:1, WHY:1, BREAKFAST1:1, WHAT1:1 |
| HELLO | 10 | 0.20 | 0.40 | 0.60 | 45.3 | BYE:2, HELLO:2, SEEM:1, CLEAN:1, FATHER:1, BREAKFAST1:1, HOSPITAL1:1, NEED:1 |
| DONTKNOW | 10 | 0.10 | 0.20 | 0.30 | 43.6 | TEACHER:2, LUNCH1:1, WANT2:1, CLOSE:1, SELL:1, BREAKFAST1:1, HELLO:1, ENOUGH:1 |
| WE | 12 | 0.08 | 0.42 | 0.42 | 69.0 | ALWAYS:2, RUN2:1, HEAR1:1, HARD:1, WALK2:1, SURE:1, HURRY:1, PAY:1 |
| LIVE2 | 12 | 0.25 | 0.33 | 0.33 | 84.8 | LIVE2:3, MEAT1:2, TOOMUCH:1, BABY1:1, LUNCH1:1, TIRED:1, WANT2:1, SORRY:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.18 | 67.0 | HERE:1, WELCOME2:1, STRONG:1, SHOP1:1, GIVE:1, YOU:1, SURE:1, BOOK:1 |

## Group Matrices - Held-Out Test Last View
### important_family_more_introduce (top1=0.76, n=50)
| true / pred | IMPORTANT | FAMILY | MORE | INTRODUCE |
|---|---:|---:|---:|---:|
| IMPORTANT | 10 | 3 | 0 | 0 |
| FAMILY | 0 | 10 | 0 | 0 |
| MORE | 0 | 0 | 11 | 0 |
| INTRODUCE | 0 | 0 | 0 | 7 |

### sell_put_decide_shop_teach (top1=0.67, n=57)
| true / pred | SELL | PUT | DECIDE1 | SHOP1 | TEACH2 |
|---|---:|---:|---:|---:|---:|
| SELL | 6 | 0 | 0 | 3 | 0 |
| PUT | 0 | 6 | 0 | 0 | 1 |
| DECIDE1 | 0 | 0 | 12 | 0 | 0 |
| SHOP1 | 4 | 0 | 0 | 4 | 1 |
| TEACH2 | 0 | 0 | 0 | 0 | 10 |

### want_many_wait_meet (top1=0.55, n=42)
| true / pred | WANT2 | MANY | WAIT | MEET |
|---|---:|---:|---:|---:|
| WANT2 | 6 | 0 | 1 | 0 |
| MANY | 2 | 6 | 0 | 0 |
| WAIT | 2 | 0 | 3 | 0 |
| MEET | 0 | 0 | 0 | 8 |

### know_hello_sell_dontknow (top1=0.61, n=44)
| true / pred | KNOW | HELLO | SELL | DONTKNOW |
|---|---:|---:|---:|---:|
| KNOW | 8 | 0 | 0 | 0 |
| HELLO | 0 | 4 | 0 | 0 |
| SELL | 0 | 0 | 6 | 0 |
| DONTKNOW | 0 | 0 | 0 | 9 |

### we_live_strong_sell (top1=0.76, n=46)
| true / pred | WE | LIVE2 | STRONG | SELL |
|---|---:|---:|---:|---:|
| WE | 12 | 0 | 0 | 0 |
| LIVE2 | 0 | 8 | 0 | 0 |
| STRONG | 0 | 0 | 9 | 0 |
| SELL | 0 | 0 | 2 | 6 |
