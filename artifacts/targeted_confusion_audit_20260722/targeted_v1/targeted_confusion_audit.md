# Targeted Confusion Audit

Model: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v1\best.keras`
Features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
FPS stress features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236_fps`

## Headline
### test
- `mean`: n=2620 top1=0.613 top3=0.825 top5=0.881
- `last`: n=2620 top1=0.587 top3=0.796 top5=0.863
- `early4`: n=2620 top1=0.077 top3=0.126 top5=0.155
- `early6`: n=2620 top1=0.140 top3=0.239 top5=0.294

### fps_val
- `mean`: n=3264 top1=0.663 top3=0.844 top5=0.887
- `last`: n=3264 top1=0.603 top3=0.804 top5=0.866
- `early4`: n=3264 top1=0.339 top3=0.507 top5=0.570
- `early6`: n=3264 top1=0.441 top3=0.635 top5=0.694

## Per-Class Held-Out Test
### View: mean
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.73 | 0.93 | 1.00 | 1.4 | IMPORTANT:11, FAMILY:3, HOUSE:1 |
| FAMILY | 12 | 0.67 | 0.92 | 1.00 | 1.5 | FAMILY:8, MANY:2, BREAKFAST1:1, IMPORTANT:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.75 | 0.83 | 0.83 | 2.1 | INTRODUCE:9, WHOLE:1, HOUSE:1, CLOTHES:1 |
| SELL | 11 | 0.55 | 1.00 | 1.00 | 1.7 | SELL:6, SHOP1:5 |
| PUT | 11 | 0.82 | 0.91 | 0.91 | 1.7 | PUT:9, SLOW:1, MOVE:1 |
| DECIDE1 | 14 | 0.86 | 0.93 | 1.00 | 1.3 | DECIDE1:12, CANNOT:1, STREET:1 |
| SHOP1 | 10 | 0.60 | 1.00 | 1.00 | 1.5 | SHOP1:6, SELL:3, INTRODUCE:1 |
| TEACH2 | 11 | 0.91 | 1.00 | 1.00 | 1.1 | TEACH2:10, TEACHER:1 |
| WANT2 | 11 | 0.55 | 0.91 | 1.00 | 1.7 | WANT2:6, WAIT:2, HERE:1, AGAIN:1, TOOMUCH:1 |
| MANY | 11 | 0.73 | 1.00 | 1.00 | 1.5 | MANY:8, CAR:1, WAIT:1, WANT2:1 |
| WAIT | 11 | 0.45 | 0.82 | 0.91 | 3.2 | WAIT:5, SAD:3, WANT2:2, NEW:1 |
| MEET | 9 | 0.78 | 0.89 | 0.89 | 1.7 | MEET:7, GIFT:1, DOWNLOAD:1 |
| KNOW | 13 | 0.54 | 0.92 | 0.92 | 1.9 | KNOW:7, LUNCH1:2, MAN:1, SEEM:1, WHY:1, SICK:1 |
| HELLO | 10 | 0.60 | 0.90 | 0.90 | 2.1 | HELLO:6, FATHER:2, BYE:1, MAN:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 0.90 | 1.5 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.92 | 0.92 | 1.00 | 1.2 | WE:11, COME:1 |
| LIVE2 | 12 | 0.75 | 0.83 | 0.92 | 2.0 | LIVE2:9, BABY1:1, TIRED:1, WHICH:1 |
| STRONG | 11 | 0.73 | 1.00 | 1.00 | 1.4 | STRONG:8, DRIVE:1, COLD:1, CAR:1 |

### View: last
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.67 | 0.80 | 0.87 | 5.7 | IMPORTANT:10, FAMILY:3, SEEM:1, TEACH2:1 |
| FAMILY | 12 | 0.67 | 0.92 | 1.00 | 1.6 | FAMILY:8, MANY:2, HOUSE:1, IMPORTANT:1 |
| MORE | 11 | 1.00 | 1.00 | 1.00 | 1.0 | MORE:11 |
| INTRODUCE | 12 | 0.67 | 0.92 | 1.00 | 1.5 | INTRODUCE:8, WHOLE:1, HAVE:1, HOW1:1, CLOTHES:1 |
| SELL | 11 | 0.45 | 0.91 | 0.91 | 2.1 | SELL:5, SHOP1:5, STRONG:1 |
| PUT | 11 | 0.55 | 0.82 | 0.82 | 4.7 | PUT:6, MOVE:2, TEACH2:1, SLOW:1, WALK2:1 |
| DECIDE1 | 14 | 0.79 | 0.93 | 0.93 | 1.5 | DECIDE1:11, MEET:1, IMPORTANT:1, ROAD:1 |
| SHOP1 | 10 | 0.50 | 0.90 | 0.90 | 2.5 | SHOP1:5, SELL:3, INTRODUCE:1, TEACH2:1 |
| TEACH2 | 11 | 1.00 | 1.00 | 1.00 | 1.0 | TEACH2:11 |
| WANT2 | 11 | 0.73 | 0.82 | 0.91 | 1.9 | WANT2:8, STREET:1, WAIT:1, HERE:1 |
| MANY | 11 | 0.55 | 0.82 | 0.91 | 3.1 | MANY:6, CAR:2, WANT2:2, NOW:1 |
| WAIT | 11 | 0.36 | 0.91 | 0.91 | 3.5 | WAIT:4, SAD:2, WANT2:2, EASY:2, NEW:1 |
| MEET | 9 | 0.89 | 0.89 | 0.89 | 1.7 | MEET:8, GIFT:1 |
| KNOW | 13 | 0.54 | 0.92 | 0.92 | 2.2 | KNOW:7, LUNCH1:4, MAN:1, WHY:1 |
| HELLO | 10 | 0.50 | 0.80 | 0.90 | 2.4 | HELLO:5, MAN:2, FATHER:2, NEVER:1 |
| DONTKNOW | 10 | 0.90 | 0.90 | 1.00 | 1.4 | DONTKNOW:9, DECIDE1:1 |
| WE | 12 | 0.83 | 1.00 | 1.00 | 1.2 | WE:10, GIVE:1, STAND2:1 |
| LIVE2 | 12 | 0.67 | 0.83 | 0.92 | 1.9 | LIVE2:8, BABY1:1, TIRED:1, WHILE:1, TRY:1 |
| STRONG | 11 | 0.82 | 1.00 | 1.00 | 1.2 | STRONG:9, DRIVE:1, CAR:1 |

### View: early4
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.20 | 0.40 | 0.40 | 53.0 | IMPORTANT:3, WANT2:2, SELL:2, EACH:2, KNOW:1, COUNTRY:1, DECIDE1:1, USE:1 |
| FAMILY | 12 | 0.00 | 0.00 | 0.25 | 63.4 | TEACHER:2, KNOW:2, SELL:2, HELLO:1, SPECIAL1:1, NOW:1, HOUSE:1, BREAKFAST1:1 |
| MORE | 11 | 0.00 | 0.00 | 0.00 | 93.0 | SELL:2, BABY1:2, WANT2:1, LUNCH1:1, SPECIAL1:1, WHAT1:1, SURE:1, GIVE:1 |
| INTRODUCE | 12 | 0.00 | 0.08 | 0.08 | 45.8 | KNOW:2, SELL:2, WANT2:2, IMPORTANT:1, HAVE:1, BOTH:1, TABLE:1, COUNTRY:1 |
| SELL | 11 | 0.36 | 0.36 | 0.45 | 54.5 | SELL:4, STILL:1, BABY1:1, MEET:1, IMPORTANT:1, EAT1:1, HELLO:1, HAPPY:1 |
| PUT | 11 | 0.09 | 0.18 | 0.18 | 55.1 | IMPORTANT:2, SHOP1:1, TOOMUCH:1, COUNTRY:1, YESTERDAY:1, THEN:1, SLOW:1, PUT:1 |
| DECIDE1 | 14 | 0.21 | 0.21 | 0.36 | 68.9 | HELLO:3, DECIDE1:3, SELL:2, LUNCH1:1, MOST:1, KNOW:1, MUCH:1, TELL:1 |
| SHOP1 | 10 | 0.30 | 0.40 | 0.40 | 38.6 | SHOP1:3, HOSPITAL1:1, IMPORTANT:1, NICE:1, MORE:1, PUT:1, SELL:1, WANT2:1 |
| TEACH2 | 11 | 0.36 | 0.36 | 0.36 | 38.1 | TEACH2:4, HELLO:2, SELL:1, KNOW:1, COUNTRY:1, TODAY:1, WINDOW:1 |
| WANT2 | 11 | 0.27 | 0.27 | 0.27 | 43.2 | KNOW:3, WANT2:3, GIVE:1, SMALL:1, SLOW:1, BUY:1, SELL:1 |
| MANY | 11 | 0.09 | 0.18 | 0.18 | 31.1 | EAT1:1, WANT2:1, HOSPITAL1:1, MOVIE1:1, HOUR:1, LETTER2:1, HOW1:1, TOUCH:1 |
| WAIT | 11 | 0.27 | 0.27 | 0.27 | 83.6 | WAIT:3, PICK:1, KNOW:1, WANT2:1, EAT1:1, COUNTRY:1, SISTER:1, HAPPY:1 |
| MEET | 9 | 0.00 | 0.00 | 0.00 | 88.9 | KNOW:2, SELL:2, BABY1:1, COUNTRY:1, WHAT1:1, MAN:1, EAT1:1 |
| KNOW | 13 | 0.15 | 0.23 | 0.31 | 23.5 | SELL:2, EAT1:2, KNOW:2, LETTER2:1, HOME:1, COUNTRY:1, HOW1:1, IF:1 |
| HELLO | 10 | 0.10 | 0.40 | 0.40 | 25.6 | SURE:1, BYE:1, IMPORTANT:1, MAN:1, YOUR:1, THINK:1, HOSPITAL1:1, KNOW:1 |
| DONTKNOW | 10 | 0.10 | 0.10 | 0.20 | 42.9 | WANT2:3, TEACHER:1, HOW1:1, YEAR:1, SURE:1, DONTKNOW:1, KNOW:1, SMALL:1 |
| WE | 12 | 0.08 | 0.08 | 0.17 | 123.7 | KNOW:2, IMPORTANT:1, ALWAYS:1, LUNCH1:1, WE:1, YES:1, PUT:1, PAY:1 |
| LIVE2 | 12 | 0.00 | 0.08 | 0.08 | 123.8 | KNOW:3, WANT2:3, HELLO:2, BABY1:1, WHILE:1, MORE:1, SELL:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 82.0 | KNOW:2, HELLO:2, STRONG:1, SHOP1:1, GIVE:1, YOU:1, SURE:1, HOW1:1 |

### View: early6
| class | n | top1 | top3 | top5 | mean true rank | top predictions |
|---|---:|---:|---:|---:|---:|---|
| IMPORTANT | 15 | 0.27 | 0.33 | 0.47 | 32.3 | IMPORTANT:4, WITH:2, COUNT:2, WANT2:1, FREE:1, SLOW:1, HOUSE:1, SELL:1 |
| FAMILY | 12 | 0.17 | 0.17 | 0.25 | 43.2 | FAMILY:2, MANY:1, KNOW:1, WANT2:1, TEACHER:1, WAIT:1, HOUSE:1, BREAKFAST1:1 |
| MORE | 11 | 0.00 | 0.09 | 0.18 | 51.1 | PARTY1:1, ON:1, SMALL:1, LUNCH1:1, SPECIAL1:1, IMPORTANT:1, WRITE:1, HERE:1 |
| INTRODUCE | 12 | 0.00 | 0.25 | 0.42 | 21.2 | PUT:2, SELL:2, COLD:1, KNOW:1, SMALL:1, BABY1:1, WANT2:1, TODAY:1 |
| SELL | 11 | 0.45 | 0.73 | 0.82 | 10.4 | SELL:5, KNOW:2, AGAIN:1, SHOP1:1, DOOR:1, SURE:1 |
| PUT | 11 | 0.18 | 0.27 | 0.36 | 26.1 | PUT:2, USE:1, BUY:1, SMALL:1, COUNTRY:1, ON:1, SLOW:1, TOOMUCH:1 |
| DECIDE1 | 14 | 0.29 | 0.29 | 0.29 | 24.9 | DECIDE1:4, LUNCH1:1, FAST:1, RUN2:1, IMPORTANT:1, HAVE:1, SEE:1, STREET:1 |
| SHOP1 | 10 | 0.30 | 0.40 | 0.40 | 34.4 | SHOP1:3, HOSPITAL1:1, YEAR:1, WHILE:1, TEACH2:1, PICK:1, SELL:1, HAVE:1 |
| TEACH2 | 11 | 0.45 | 0.45 | 0.55 | 17.9 | TEACH2:5, SELL:2, MOST:1, YEAR:1, SHOP1:1, CLOTHES:1 |
| WANT2 | 11 | 0.27 | 0.36 | 0.55 | 49.8 | WANT2:3, SELL:2, LETTER2:1, NOW:1, CAR:1, IMPORTANT:1, ENTER:1, EAT1:1 |
| MANY | 11 | 0.18 | 0.27 | 0.36 | 35.5 | MANY:2, LOVE:1, HAVE:1, HOSPITAL1:1, SELL:1, SHOP1:1, CAKE:1, TODAY:1 |
| WAIT | 11 | 0.18 | 0.36 | 0.36 | 83.6 | WAIT:2, SORRY:1, KNOW:1, WANT2:1, WITH:1, MORE:1, SISTER:1, GOOD:1 |
| MEET | 9 | 0.22 | 0.56 | 0.56 | 46.0 | MEET:2, TO:2, WHILE:1, YEAR:1, HURRY:1, SURE:1, EAT1:1 |
| KNOW | 13 | 0.38 | 0.54 | 0.62 | 22.6 | KNOW:5, HELLO:2, TOMORROW:1, ANY:1, LUNCH1:1, WHY:1, SURE:1, WHAT1:1 |
| HELLO | 10 | 0.20 | 0.60 | 0.70 | 38.7 | BYE:2, HELLO:2, SEEM:1, CLEAN:1, FATHER:1, BREAKFAST1:1, HOSPITAL1:1, HUSBAND:1 |
| DONTKNOW | 10 | 0.20 | 0.20 | 0.30 | 41.9 | DONTKNOW:2, TEACHER:1, LUNCH1:1, WANT2:1, CLOSE:1, SELL:1, BREAKFAST1:1, HELLO:1 |
| WE | 12 | 0.08 | 0.42 | 0.42 | 75.1 | KNOW:3, ALWAYS:2, HARD:1, WALK2:1, SURE:1, ENTER:1, PAY:1, WE:1 |
| LIVE2 | 12 | 0.25 | 0.33 | 0.33 | 77.2 | LIVE2:3, MEAT1:2, TOOMUCH:1, BABY1:1, KNOW:1, TIRED:1, WANT2:1, SORRY:1 |
| STRONG | 11 | 0.09 | 0.09 | 0.09 | 69.5 | SELL:2, HERE:1, WELCOME2:1, STRONG:1, SHOP1:1, GIVE:1, YOU:1, SURE:1 |

## Group Matrices - Held-Out Test Last View
### important_family_more_introduce (top1=0.74, n=50)
| true / pred | IMPORTANT | FAMILY | MORE | INTRODUCE |
|---|---:|---:|---:|---:|
| IMPORTANT | 10 | 3 | 0 | 0 |
| FAMILY | 1 | 8 | 0 | 0 |
| MORE | 0 | 0 | 11 | 0 |
| INTRODUCE | 0 | 0 | 0 | 8 |

### sell_put_decide_shop_teach (top1=0.67, n=57)
| true / pred | SELL | PUT | DECIDE1 | SHOP1 | TEACH2 |
|---|---:|---:|---:|---:|---:|
| SELL | 5 | 0 | 0 | 5 | 0 |
| PUT | 0 | 6 | 0 | 0 | 1 |
| DECIDE1 | 0 | 0 | 11 | 0 | 0 |
| SHOP1 | 3 | 0 | 0 | 5 | 1 |
| TEACH2 | 0 | 0 | 0 | 0 | 11 |

### want_many_wait_meet (top1=0.62, n=42)
| true / pred | WANT2 | MANY | WAIT | MEET |
|---|---:|---:|---:|---:|
| WANT2 | 8 | 0 | 1 | 0 |
| MANY | 2 | 6 | 0 | 0 |
| WAIT | 2 | 0 | 4 | 0 |
| MEET | 0 | 0 | 0 | 8 |

### know_hello_sell_dontknow (top1=0.59, n=44)
| true / pred | KNOW | HELLO | SELL | DONTKNOW |
|---|---:|---:|---:|---:|
| KNOW | 7 | 0 | 0 | 0 |
| HELLO | 0 | 5 | 0 | 0 |
| SELL | 0 | 0 | 5 | 0 |
| DONTKNOW | 0 | 0 | 0 | 9 |

### we_live_strong_sell (top1=0.70, n=46)
| true / pred | WE | LIVE2 | STRONG | SELL |
|---|---:|---:|---:|---:|
| WE | 10 | 0 | 0 | 0 |
| LIVE2 | 0 | 8 | 0 | 0 |
| STRONG | 0 | 0 | 9 | 0 |
| SELL | 0 | 0 | 1 | 5 |
