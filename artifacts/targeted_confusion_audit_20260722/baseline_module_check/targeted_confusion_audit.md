# Targeted Confusion Audit

Model: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30\best.keras`
Features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
FPS stress features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236_fps`

## Headline
### test
- `mean`: n=2620 top1=0.617 top3=0.817 top5=0.868
- `last`: n=2620 top1=0.571 top3=0.790 top5=0.853
- `early4`: n=2620 top1=0.081 top3=0.130 top5=0.159
- `early6`: n=2620 top1=0.137 top3=0.237 top5=0.285

### fps_val
- `mean`: n=3264 top1=0.640 top3=0.828 top5=0.880
- `last`: n=3264 top1=0.588 top3=0.790 top5=0.859
- `early4`: n=3264 top1=0.326 top3=0.499 top5=0.558
- `early6`: n=3264 top1=0.430 top3=0.616 top5=0.681

## Per-Class Held-Out Test
### View: mean
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 1.00 | 1.00 | 1.4 | IMPORTANT:10, FAMILY:3, TEACH2:1, CLOSE:1 |
| FAMILY | 12 | 0.75 | 0.92 | 1.00 | 1.6 | FAMILY:9, MANY:2, BREAKFAST1:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.67 | 0.75 | 0.83 | 2.5 | INTRODUCE:8, WHOLE:1, NEW:1, WITH:1, CLOTHES:1 |
| SELL | 11 | 0.36 | 0.73 | 0.82 | 2.6 | SELL:4, STRONG:4, SHOP1:3 |
| PUT | 11 | 0.64 | 0.91 | 0.91 | 2.1 | PUT:7, MOVE:2, HOW1:1, SLOW:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 1.00 | 1.4 | DECIDE1:12, CANNOT:1, STREET:1 |
| SHOP1 | 10 | 0.60 | 1.00 | 1.00 | 1.6 | SHOP1:6, SELL:2, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.45 | 0.73 | 0.73 | 3.5 | WANT2:5, HERE:2, WHAT1:1, WAIT:1, MANY:1, TOOMUCH:1 |
| MANY | 11 | 0.82 | 0.91 | 1.00 | 1.4 | MANY:9, DRIVE:1, WAIT:1 |
| WAIT | 11 | 0.73 | 0.91 | 0.91 | 2.5 | WAIT:8, SAD:2, WHAT1:1 |
| MEET | 9 | 0.78 | 0.89 | 1.00 | 1.6 | MEET:7, GIFT:1, DOWNLOAD:1 |
| KNOW | 13 | 0.15 | 0.69 | 0.77 | 4.5 | LUNCH1:3, WHY:3, SEEM:3, KNOW:2, MAN:1, BECAUSE:1 |
| HELLO | 10 | 0.40 | 0.70 | 0.90 | 2.7 | HELLO:4, SEEM:2, FATHER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.6 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 1.00 | 1.00 | 1.2 | WE:11, GIVE:1 |
| LIVE2 | 12 | 0.83 | 0.92 | 1.00 | 1.5 | LIVE2:10, WHICH:2 |
| STRONG | 11 | 0.73 | 1.00 | 1.00 | 1.3 | STRONG:8, DRIVE:1, COLD:1, CAR:1 |

### View: last
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 0.87 | 0.87 | 5.8 | IMPORTANT:10, FAMILY:3, SEEM:1, TEACH2:1 |
| FAMILY | 12 | 0.75 | 0.92 | 0.92 | 1.7 | FAMILY:9, MANY:1, BREAKFAST1:1, IMPORTANT:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.67 | 0.83 | 0.92 | 2.7 | INTRODUCE:8, WHOLE:1, HAVE:1, HOW1:1, CLOTHES:1 |
| SELL | 11 | 0.27 | 0.73 | 0.91 | 2.7 | SHOP1:4, SELL:3, STRONG:3, TEACHER:1 |
| PUT | 11 | 0.45 | 0.73 | 0.82 | 5.6 | PUT:5, MOVE:2, HOW1:1, TEACH2:1, SLOW:1, JUMP:1 |
| DECIDE1 | 14 | 0.79 | 0.93 | 0.93 | 1.6 | DECIDE1:11, ENTER:1, MEET:1, STREET:1 |
| SHOP1 | 10 | 0.60 | 0.70 | 0.90 | 2.5 | SHOP1:6, SELL:2, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.36 | 0.64 | 0.73 | 4.8 | WANT2:4, STREET:2, NOW:1, WAIT:1, HERE:1, MANY:1, TOOMUCH:1 |
| MANY | 11 | 0.73 | 0.91 | 1.00 | 1.6 | MANY:8, CAR:1, WAIT:1, WANT2:1 |
| WAIT | 11 | 0.64 | 0.82 | 0.91 | 2.6 | WAIT:7, SAD:1, RIGHT3:1, EASY:1, NEW:1 |
| MEET | 9 | 0.89 | 1.00 | 1.00 | 1.2 | MEET:8, GIFT:1 |
| KNOW | 13 | 0.15 | 0.69 | 0.92 | 4.4 | LUNCH1:4, WHY:3, KNOW:2, BECAUSE:2, SEEM:2 |
| HELLO | 10 | 0.30 | 0.50 | 0.80 | 4.2 | HELLO:3, SEEM:2, FATHER:2, BYE:1, MAN:1, HOSPITAL1:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 1.00 | 1.4 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 1.00 | 1.00 | 1.00 | 1.0 | WE:12 |
| LIVE2 | 12 | 0.75 | 0.83 | 0.92 | 1.8 | LIVE2:9, WHICH:1, WHILE:1, TRY:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: early4
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.07 | 0.20 | 0.27 | 61.3 | EAT1:1, COUNTRY:1, WHILE:1, CLOTHES:1, DECIDE1:1, USE:1, IMPORTANT:1, TODAY:1 |
| FAMILY | 12 | 0.00 | 0.00 | 0.17 | 57.6 | TEACHER:2, WHILE:2, MOUTH:1, MEET:1, SPECIAL1:1, HOW1:1, HOUSE:1, BREAKFAST1:1 |
| MORE | 11 | 0.00 | 0.00 | 0.09 | 77.5 | HAVE:1, FAST:1, EAT1:1, LUNCH1:1, SPECIAL1:1, WHAT1:1, THEN:1, SURE:1 |
| INTRODUCE | 12 | 0.00 | 0.08 | 0.08 | 75.5 | EAT1:2, STREET:1, HAVE:1, TABLE:1, TIME:1, CANNOT:1, WHILE:1, HERE:1 |
| SELL | 11 | 0.18 | 0.18 | 0.27 | 87.5 | MEET:2, SELL:2, SLOW:1, IMPORTANT:1, STRONG:1, WHILE:1, EAT1:1, TOMORROW:1 |
| PUT | 11 | 0.09 | 0.09 | 0.09 | 119.0 | YOU:1, HOW1:1, SAME2:1, IN:1, ALWAYS:1, WHILE:1, SLOW:1, PUT:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.36 | 63.9 | DECIDE1:3, LUNCH1:1, FAST:1, WHILE:1, HELLO:1, HOW1:1, ONE:1, CANNOT:1 |
| SHOP1 | 10 | 0.30 | 0.30 | 0.40 | 78.5 | SHOP1:3, HOSPITAL1:1, YEAR:1, WHAT1:1, MORE:1, CHAIR:1, HOW1:1, TOUCH:1 |
| TEACH2 | 11 | 0.36 | 0.36 | 0.36 | 39.4 | TEACH2:4, GIFT:1, BYE:1, WHILE:1, KNOW:1, COUNTRY:1, TODAY:1, THEN:1 |
| WANT2 | 11 | 0.09 | 0.09 | 0.18 | 83.2 | HAVE:2, CANNOT:1, GIVE:1, WANT2:1, WHILE:1, SLOW:1, BUY:1, TODAY:1 |
| MANY | 11 | 0.09 | 0.09 | 0.09 | 49.8 | EAT1:1, WHILE:1, HOSPITAL1:1, MOUTH:1, HOUR:1, LETTER2:1, HOW1:1, TOUCH:1 |
| WAIT | 11 | 0.27 | 0.27 | 0.27 | 91.5 | WAIT:3, YOU:1, ABOUT2:1, CLOTHES:1, EAT1:1, SLOW:1, SISTER:1, HAPPY:1 |
| MEET | 9 | 0.00 | 0.00 | 0.00 | 83.3 | SORRY:1, HOSPITAL1:1, NOW:1, WHAT1:1, NEED:1, CANNOT:1, HOW1:1, MOUTH:1 |
| KNOW | 13 | 0.00 | 0.00 | 0.00 | 108.4 | EAT1:3, HOW1:2, GIVE:1, HOME:1, IN:1, WHILE:1, THINK:1, ALWAYS:1 |
| HELLO | 10 | 0.10 | 0.20 | 0.20 | 69.2 | SURE:1, BYE:1, TOMORROW:1, MAN:1, YOUR:1, THINK:1, TIME:1, SIT:1 |
| DONTKNOW | 10 | 0.10 | 0.10 | 0.20 | 47.8 | TEACHER:1, HOW1:1, WHAT1:1, FAST:1, CLOTHES:1, YEAR:1, SURE:1, DONTKNOW:1 |
| WE | 12 | 0.08 | 0.17 | 0.17 | 113.5 | PAY:2, CANNOT:1, ALWAYS:1, LUNCH1:1, WE:1, YES:1, HOW1:1, TIME:1 |
| LIVE2 | 12 | 0.00 | 0.08 | 0.08 | 104.5 | MEET:2, WHILE:2, MONTH:1, CAKE:1, EAT1:1, MORE:1, MOUTH:1, NICE:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 92.7 | CANNOT:2, STRONG:1, WHILE:1, GIVE:1, YOU:1, SURE:1, TOMORROW:1, HOW1:1 |

### View: early6
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.13 | 0.33 | 0.40 | 35.9 | COUNT:2, IMPORTANT:2, WITH:1, SAME2:1, THEN:1, FREE:1, SLOW:1, MORE:1 |
| FAMILY | 12 | 0.17 | 0.17 | 0.25 | 37.2 | FAMILY:2, TEACHER:2, MANY:1, ALWAYS:1, WANT2:1, WAIT:1, BED2:1, IMPORTANT:1 |
| MORE | 11 | 0.09 | 0.18 | 0.27 | 35.6 | PARTY1:1, ON:1, SMALL:1, HARD:1, SPECIAL1:1, MORE:1, CONGRATULATIONS:1, HERE:1 |
| INTRODUCE | 12 | 0.08 | 0.17 | 0.25 | 32.8 | COLD:1, CANNOT:1, CLOTHES:1, SMALL:1, RUN2:1, CHILD:1, USE:1, SELL:1 |
| SELL | 11 | 0.27 | 0.45 | 0.64 | 25.6 | SELL:3, CAR:2, PLAY:1, AGAIN:1, EAT1:1, SHOP1:1, WHERE:1, SURE:1 |
| PUT | 11 | 0.09 | 0.09 | 0.09 | 48.1 | SLOW:2, MORE:2, USE:1, DAY:1, ON:1, ABOUT2:1, PUT:1, OPEN:1 |
| DECIDE1 | 14 | 0.21 | 0.29 | 0.29 | 28.1 | DECIDE1:3, LUNCH1:1, FAST:1, RUN2:1, MAN:1, TEACH2:1, HAVE:1, SEE:1 |
| SHOP1 | 10 | 0.30 | 0.40 | 0.40 | 53.2 | SHOP1:3, HOSPITAL1:1, YEAR:1, WHILE:1, TEACH2:1, PICK:1, SAD:1, HAVE:1 |
| TEACH2 | 11 | 0.45 | 0.45 | 0.45 | 18.7 | TEACH2:5, BUY:1, SELL:1, BYE:1, YEAR:1, TEACHER:1, CLOTHES:1 |
| WANT2 | 11 | 0.09 | 0.27 | 0.27 | 66.4 | HAVE:2, CAR:2, HOUR:1, NOW:1, WANT2:1, WHAT1:1, SAME2:1, ENTER:1 |
| MANY | 11 | 0.18 | 0.27 | 0.27 | 44.3 | MANY:2, LOVE:1, HAVE:1, HOSPITAL1:1, HERE:1, SHOP1:1, ONE:1, CAKE:1 |
| WAIT | 11 | 0.27 | 0.36 | 0.36 | 83.3 | WAIT:3, SORRY:1, EAT1:1, OFFICE:1, MORE:1, SISTER:1, GOOD:1, YEAR:1 |
| MEET | 9 | 0.22 | 0.44 | 0.56 | 43.6 | MEET:2, WHILE:1, YEAR:1, TO:1, CLOSE:1, VERY:1, ASK:1, EAT1:1 |
| KNOW | 13 | 0.00 | 0.15 | 0.15 | 56.2 | SEEM:2, IF:1, TOMORROW:1, HOME:1, ANY:1, LUNCH1:1, BECAUSE:1, BED2:1 |
| HELLO | 10 | 0.10 | 0.30 | 0.50 | 51.9 | SEEM:3, BYE:1, YEAR:1, FATHER:1, BREAKFAST1:1, HOSPITAL1:1, NEED:1, HELLO:1 |
| DONTKNOW | 10 | 0.10 | 0.30 | 0.30 | 47.4 | TEACHER:2, CLOSE:2, LUNCH1:1, HAVE:1, BREAKFAST1:1, SURE:1, ENOUGH:1, DONTKNOW:1 |
| WE | 12 | 0.08 | 0.33 | 0.42 | 70.8 | ALWAYS:2, CANNOT:1, HEAR1:1, HARD:1, WALK2:1, SURE:1, ENTER:1, PAY:1 |
| LIVE2 | 12 | 0.33 | 0.33 | 0.33 | 67.7 | LIVE2:4, TOOMUCH:1, BABY1:1, EAT1:1, MEAT1:1, BIG:1, SORRY:1, WHAT1:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 69.6 | HERE:1, RUN2:1, STRONG:1, SHOP1:1, GIVE:1, YOU:1, SURE:1, WHAT1:1 |

## Group Matrices - Held-Out Test Last View
### important_family_more_introduce (top1=0.76, n=50)
| true / pred | IMPORTANT | FAMILY | MORE | INTRODUCE |
|---|---:|---:|---:|---:|
| IMPORTANT | 10 | 3 | 0 | 0 |
| FAMILY | 1 | 9 | 0 | 0 |
| MORE | 0 | 0 | 11 | 0 |
| INTRODUCE | 0 | 0 | 0 | 8 |

### sell_put_decide_shop_teach (top1=0.61, n=57)
| true / pred | SELL | PUT | DECIDE1 | SHOP1 | TEACH2 |
|---|---:|---:|---:|---:|---:|
| SELL | 3 | 0 | 0 | 4 | 0 |
| PUT | 0 | 5 | 0 | 0 | 1 |
| DECIDE1 | 0 | 0 | 11 | 0 | 0 |
| SHOP1 | 2 | 0 | 0 | 6 | 1 |
| TEACH2 | 0 | 0 | 0 | 0 | 10 |

### want_many_wait_meet (top1=0.64, n=42)
| true / pred | WANT2 | MANY | WAIT | MEET |
|---|---:|---:|---:|---:|
| WANT2 | 4 | 1 | 1 | 0 |
| MANY | 1 | 8 | 1 | 0 |
| WAIT | 0 | 0 | 7 | 0 |
| MEET | 0 | 0 | 0 | 8 |

### know_hello_sell_dontknow (top1=0.39, n=44)
| true / pred | KNOW | HELLO | SELL | DONTKNOW |
|---|---:|---:|---:|---:|
| KNOW | 2 | 0 | 0 | 0 |
| HELLO | 0 | 3 | 0 | 0 |
| SELL | 0 | 0 | 3 | 0 |
| DONTKNOW | 0 | 0 | 0 | 9 |

### we_live_strong_sell (top1=0.72, n=46)
| true / pred | WE | LIVE2 | STRONG | SELL |
|---|---:|---:|---:|---:|
| WE | 12 | 0 | 0 | 0 |
| LIVE2 | 0 | 9 | 0 | 0 |
| STRONG | 0 | 0 | 9 | 0 |
| SELL | 0 | 0 | 3 | 3 |
