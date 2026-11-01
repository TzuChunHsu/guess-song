#!/usr/bin/env python3
"""Inject the song bank, a T->S char map and artist aliases into the game template."""
import json, os, sys, opencc

ALIASES = {
    "鄧麗君": ["Teresa Teng"], "蔡琴": ["Tsai Chin"], "費玉清": ["Fei Yu-Ching", "Yu-Ching Fei"],
    "蘇芮": ["Julie Sue"], "羅大佑": ["Lo Ta-Yu", "Lo Ta-You"], "鳳飛飛": ["Fong Fei-Fei"],
    "費翔": ["Kris Phillips", "Fei Xiang"], "齊秦": ["Chyi Chin"], "王傑": ["Dave Wang"],
    "張雨生": ["Tom Chang"], "陳淑樺": ["Sarah Chen"], "姜育恆": ["Chiang Yu-Heng"],
    "童安格": ["Angus Tung"], "潘美辰": ["Pan Mei-Chen"], "小虎隊": ["Little Tigers"],
    "趙傳": ["Chao Chuan"], "黃鶯鶯": ["Tracy Huang"], "庾澄慶": ["Harlem Yu"],
    "黃品源": ["Huang Pin-Yuan"], "郭富城": ["Aaron Kwok"], "葉蒨文": ["Sally Yeh"],
    "黎明": ["Leon Lai"], "周華健": ["Wakin Chau", "Emil Chau"], "劉德華": ["Andy Lau"],
    "鄭智化": ["Cheng Chih-Hua", "Zheng Zhihua"], "陳昇": ["Bobby Chen"], "李宗盛": ["Jonathan Lee"],
    "孟庭葦": ["Meng Ting-Wei", "Mavis Meng"], "黃安": ["Huang An"], "張學友": ["Jacky Cheung"],
    "張信哲": ["Jeff Chang"], "張宇": ["Phil Chang"], "那英": ["Na Ying"], "辛曉琪": ["Winnie Hsin"],
    "萬芳": ["Wan Fang"], "伍佰": ["Wu Bai"], "王菲": ["Faye Wong"], "陳奕迅": ["Eason Chan"],
    "許茹芸": ["Valen Hsu"], "許美靜": ["Mavis Hee"], "熊天平": ["Xiong Tianping"],
    "任賢齊": ["Richie Jen", "Richie Ren"], "張惠妹": ["A-Mei", "aMEI"], "陶喆": ["David Tao"],
    "張震嶽": ["A-Yue", "Chang Chen-Yue"], "蔡健雅": ["Tanya Chua"], "莫文蔚": ["Karen Mok"],
    "李翊君": ["Li Yi-Jun"], "劉若英": ["Rene Liu"], "江美琪": ["Maggie Chiang"],
    "五月天": ["Mayday"], "朴樹": ["Pu Shu"], "林憶蓮": ["Sandy Lam"], "周傳雄": ["Steve Chou"],
    "迪克牛仔": ["Dick Cowboy"], "蕭亞軒": ["Elva Hsiao"], "李玟": ["CoCo Lee"],
    "孫燕姿": ["Stefanie Sun"], "梁靜茹": ["Fish Leong"], "周杰倫": ["Jay Chou"],
    "光良": ["Michael Wong"], "王力宏": ["Leehom Wang", "Wang Leehom"], "S.H.E": ["SHE"],
    "信樂團": ["Shin Band"], "戴佩妮": ["Penny Tai"], "李聖傑": ["Sam Lee"], "蔡依林": ["Jolin Tsai"],
    "范瑋琪": ["Christine Fan"], "林俊傑": ["JJ Lin"], "陳綺貞": ["Cheer Chen"],
    "張韶涵": ["Angela Chang"], "王心凌": ["Cyndi Wang"], "潘瑋柏": ["Will Pan"],
    "飛兒樂團": ["F.I.R."], "弦子": ["Xian Zi"], "楊丞琳": ["Rainie Yang"], "蕭煌奇": ["Ricky Hsiao"],
    "蘇打綠": ["Sodagreen"], "張懸": ["Deserts Chang"], "楊培安": ["Roger Yang"],
    "羅志祥": ["Show Lo"], "盧廣仲": ["Crowd Lu"], "楊宗緯": ["Aska Yang"], "林宥嘉": ["Yoga Lin"],
    "蕭敬騰": ["Jam Hsiao"], "黃小琥": ["Tiger Huang"], "徐佳瑩": ["LaLa Hsu"], "汪峰": ["Wang Feng"],
    "田馥甄": ["Hebe Tien"], "曲婉婷": ["Wanting"], "鄧紫棋": ["G.E.M.", "GEM"],
    "宋冬野": ["Song Dongye"], "薛之謙": ["Joker Xue"], "周興哲": ["Eric Chou"], "趙雷": ["Zhao Lei"],
    "毛不易": ["Mao Buyi"], "李榮浩": ["Li Ronghao", "Ronghao Li"], "告五人": ["Accusefive"],
    "齊豫": ["Chyi Yu"], "李建復": ["Lee Chien-Fu"], "崔健": ["Cui Jian"], "草蜢": ["Grasshopper"],
    "高勝美": ["Gao Sheng-Mei"], "毛寧": ["Mao Ning"], "李春波": ["Li Chunbo"], "邰正宵": ["Samuel Tai"],
    "趙詠華": ["Cyndi Chaw"], "老狼": ["Lao Lang"], "鄭鈞": ["Zheng Jun"], "范曉萱": ["Mavis Fan"],
    "動力火車": ["Power Station"], "林曉培": ["Shino Lin"], "溫嵐": ["Landy Wen"], "許巍": ["Xu Wei"],
    "龐龍": ["Pang Long"], "刀郎": ["Dao Lang"], "黃義達": ["Huang Yi-Da"], "金莎": ["Kym"],
    "郭靜": ["Claire Kuo"], "張芸京": ["Jing Chang"], "鳳凰傳奇": ["Phoenix Legend"], "筷子兄弟": ["Chopstick Brothers"],
    "魏如昀": ["Queen Wei"], "馬頔": ["Ma Di"], "謝和弦": ["R-Chord"], "李佳薇": ["Jess Lee"],
    "周湯豪": ["Nick Chou"], "張碧晨": ["Zhang Bichen"], "周深": ["Zhou Shen", "Charlie Zhou Shen"], "大壯": ["Da Zhuang"], "八三夭": ["831"],
    # 台語
    "葉啟田": ["Yeh Chi-Tien"], "沈文程": ["Shen Wen-Cheng"], "文夏": ["Wen Hsia"], "陳小雲": ["Chen Hsiao-Yun"],
    "江蕙": ["Jody Chiang"], "蔡秋鳳": ["Tsai Chiu-Feng"], "陳雷": ["Chen Lei"], "林強": ["Lim Giong"],
    "張秀卿": ["Chang Hsiu-Ching"], "陳盈潔": ["Chen Ying-Chieh"], "黃妃": ["Huang Fei"], "謝金燕": ["Jeannie Hsieh"],
    "茄子蛋": ["EggPlantEgg"], "洪榮宏": ["Hung Jung-Hung"], "吳淑敏": ["Wu Shu-Min"], "施文彬": ["Shih Wen-Pin"],
    "蔡小虎": ["Tsai Hsiao-Hu"], "王識賢": ["Wang Shih-Hsien"], "金門王": ["Kinmen Wang"], "李炳輝": ["Li Ping-Hui"],
    "阿密特": ["A-MIT", "張惠妹", "aMEI"], "翁立友": ["Weng Li-You"], "滅火器": ["Fire EX."], "珂拉琪": ["Collage"],
    "陳芬蘭": ["Chen Fen-Lan"], "洪一峰": ["Hong Yi-Feng"],
    "黃乙玲": ["Huang Yee-Ling", "Huang Yi-Ling"], "阿杜": ["A-Do", "A Do"], "孫淑媚": ["Sun Shu-Mei"],
    "李千娜": ["Lee Chien-Na", "李千那"], "玖壹壹": ["Nine One One", "911"], "許富凱": ["Hsu Fu-Kai"], "盧廣仲": ["Crowd Lu"],
    "曾瑋中": ["Tseng Wei-Chung"], "邱軍": ["Chiu Chun"], "黃奇斌": ["Huang Chi-Pin", "阿斌"],
    "伍思凱": ["Sky Wu"], "南拳媽媽": ["Nan Quan Mama"], "吳克群": ["Kenji Wu"], "吳宗憲": ["Jacky Wu"],
    "張國榮": ["Leslie Cheung"], "張棟樑": ["Nicholas Teo"], "張艾嘉": ["Sylvia Chang"], "彭佳慧": ["Julia Peng"],
    "徐懷鈺": ["Yuki Hsu"], "方大同": ["Khalil Fong"], "曹格": ["Gary Chaw"], "李健": ["Li Jian"],
    "林志炫": ["Terry Lin"], "梁詠琪": ["Gigi Leung"], "梅艷芳": ["Anita Mui"], "無印良品": ["Michael & Victor"],
    "熱狗": ["MC HotDog", "MC Hot Dog"], "胡夏": ["Hu Xia"], "范逸臣": ["Van Fan"], "草東沒有派對": ["No Party For Cao Dong"],
    "蔡旻佑": ["Evan Yo"], "陳勢安": ["Andrew Tan"], "陳慧琳": ["Kelly Chen"], "陳華": ["Chen Hua"],
    "黃大煒": ["David Huang"], "黃舒駿": ["Huang Shu-Chun"],
    "尤雅": ["You Ya"], "劉文正": ["Liu Wen-Cheng", "Steven Liu"], "王夢麟": ["Wang Meng-Lin"], "鄭怡": ["Cheng Yi"],
    "王芷蕾": ["Wang Chih-Lei"], "崔健": ["Cui Jian"], "甄妮": ["Jenny Tseng"], "潘越雲": ["Pan Yueh-Yun"],
    "張清芳": ["Stella Chang"], "林志穎": ["Jimmy Lin"], "張洪量": ["Chang Hung-Liang"], "毛寧": ["Mao Ning"],
    "老狼": ["Lao Lang"], "裘海正": ["Chiu Hai-Cheng"], "巫啟賢": ["Eric Moo"], "張衛健": ["Dicky Cheung"],
    "蘇慧倫": ["Tarcy Su"], "蘇永康": ["William So"], "周蕙": ["Where Chou"], "謝霆鋒": ["Nicholas Tse"],
    "阿桑": ["A-Sun"], "胡彥斌": ["Tiger Hu"], "林依晨": ["Ariel Lin"], "陳小春": ["Jordan Chan"],
    "容祖兒": ["Joey Yung"], "蔡淳佳": ["Joi Chua"], "李玖哲": ["Nicky Lee"], "戴愛玲": ["Princess Ai"],
    "黃義達": ["Huang Yi-Da"], "飛輪海": ["Fahrenheit"], "丁噹": ["Della"], "張靚穎": ["Jane Zhang"],
    "黃鴻升": ["Alien Huang"], "李佳薇": ["Jess Lee"], "逃跑計劃": ["Escape Plan"], "王錚亮": ["Wang Zhengliang"],
    "馬頔": ["Ma Di"],
    "黃明志": ["Namewee"], "大壯": ["Da Zhuang"], "小潘潘": ["Xiao Pan Pan"], "小峰峰": ["Xiao Feng Feng"],
    "任然": ["Ren Ran"], "夢然": ["Miya"], "吳青峰": ["Qing Feng Wu", "青峰"], "陳雪凝": ["Chen Xue Ning"],
    "阿冗": ["A Rong"], "高爾宣": ["OSN", "高爾宣 OSN"], "瘦子E.SO": ["E.SO", "瘦子"], "許光漢": ["Greg Hsu"],
    "艾怡良": ["Eve Ai"], "張遠": ["Zhang Yuan"], "小阿七": ["Xiao A Qi"], "詹雯婷": ["Faye"],
    "孫盛希": ["Shi Shi"], "理想混蛋": ["Bestards"], "承桓": ["Cheng Huan"], "菲道爾": ["Firdhaus"],
    "大穎": ["DIOR 大穎", "DIOR"], "盧盧快閉嘴": ["LuLu"], "王宇宙Leto": ["Leto", "王宇宙"], "喬浚丞": ["Chiao Chun-Cheng"],
    "派偉俊": ["Patrick Brasca"], "李浩瑋": ["Howard Lee"], "邱鋒澤": ["Feng Ze"], "艾薇": ["Ivy"],
    "JOYCE就以斯": ["JOYCE", "就以斯"], "美秀集團": ["Amazing Show"], "LBI利比": ["LBI", "利比"], "于冬然": ["Yu Dong Ran"],
    "羽泉": ["Yu Quan"], "楊乃文": ["Naiwen Yang"], "水木年華": ["Shui Mu Nian Hua"], "可米小子": ["Comic Boyz"],
    "許巍": ["Xu Wei"], "楊坤": ["Yang Kun"], "林凡": ["Freya Lim"], "梁文音": ["Rachel Liang"], "許嵩": ["Vae Xu", "Vae"],
    "張杰": ["Jason Zhang"], "華晨宇": ["Hua Chenyu"], "郁可唯": ["Yisa Yu"], "金玟岐": ["Jin Wen Qi"], "黃霄雲": ["Huang Xiaoyun"],
    "于文文": ["Kelly Yu"], "井朧": ["Jing Long"], "余天": ["Yu Tian"], "劉佳慧": ["Liu Chia-Hui"], "劉歡": ["Liu Huan"],
    "劉福助": ["Liu Fu-Chu"], "吳奇隆": ["Nicky Wu"], "周筆暢": ["Bibi Zhou"], "品冠": ["Victor Wong"], "唐朝": ["Tang Dynasty"],
    "唐磊": ["Tang Lei"], "姚蘇蓉": ["Yao Su-Rong"], "孫悅": ["Sun Yue"], "孫楠": ["Sun Nan"], "寶石Gem": ["GEM", "寶石"],
    "屠洪剛": ["Tu Honggang"], "張含韻": ["Zhang Hanyun"], "徐曉菁": ["Hsu Hsiao-Ching"], "李娜": ["Li Na"], "李宇春": ["Chris Lee"],
    "李玉剛": ["Li Yugang"], "楊芳儀": ["Yang Fang-Yi"], "楊鈺瑩": ["Yang Yuying"], "江淑娜": ["Chiang Shu-Na"], "汪蘇瀧": ["Silence Wang"],
    "海來阿木": ["Hailai Amu"], "游鴻明": ["Chris Yu"], "潘安邦": ["Pan An-Bang"], "王強": ["Wang Qiang"], "王貳浪": ["Wang Er Lang"],
    "王靖雯": ["Wang Jingwen"], "王馨平": ["Linda Wong"], "田震": ["Tian Zhen"], "胡歌": ["Hu Ge"], "艾辰": ["Ai Chen"],
    "葉佳修": ["Yeh Chia-Hsiu"], "董事長樂團": ["The Chairman"], "蘇運瑩": ["Su Yunying"], "袁婭維": ["Tia Ray"], "謝雷": ["Hsieh Lei"],
    "趙薇": ["Vicki Zhao"], "郭金發": ["Kuo Chin-Fa"], "金智娟": ["娃娃", "Wawa"], "銀霞": ["Yin Hsia"], "阿吉仔": ["A-Ji-A"],
    "陳一郎": ["Chen I-Lang"], "陳明章": ["Chen Ming-Chang"], "陳曉東": ["Daniel Chan"], "陳紅": ["Chen Hong"], "陶晶瑩": ["Matilda Tao"],
    "隔壁老樊": ["Ge Bi Lao Fan"], "韓紅": ["Han Hong"], "騰格爾": ["Tengger"], "高慧君": ["Kao Hui-Chun"], "高楓": ["Gao Feng"],
    "黃一飛": ["Huang Yi-Fei"], "黃西田": ["Huang Hsi-Tien"], "黑豹": ["Black Panther"],
    "許冠傑": ["Sam Hui"], "羅文": ["Roman Tam"], "葉麗儀": ["Frances Yip"], "陳百強": ["Danny Chan"], "譚詠麟": ["Alan Tam"],
    "徐小鳳": ["Paula Tsui"], "林子祥": ["George Lam"], "李克勤": ["Hacken Lee"], "陳慧嫻": ["Priscilla Chan"], "草蜢": ["Grasshopper"],
    "葉蒨文": ["Sally Yeh"], "關淑怡": ["Shirley Kwan"], "劉德華": ["Andy Lau"], "黎明": ["Leon Lai"], "周慧敏": ["Vivian Chow"],
    "郭富城": ["Aaron Kwok"], "楊千嬅": ["Miriam Yeung"], "鄭秀文": ["Sammi Cheng"], "容祖兒": ["Joey Yung"], "鄭中基": ["Ronald Cheng"],
    "側田": ["Justin Lo"], "張敬軒": ["Hins Cheung"], "李泳知": ["Lee Young Ji", "이영지"], "サザンオールスターズ": ["Southern All Stars"],
    "松任谷由実": ["Yumi Matsutoya"], "和田光司": ["Koji Wada"], "星野源": ["Gen Hoshino"], "ゆず": ["Yuzu"], "レミオロメン": ["Remioromen"],
    "ヨルシカ": ["Yorushika"], "凛として時雨": ["Ling tosite sigure"], "TK from 凛として時雨": ["TK"],
    # 韓語
    "少女時代": ["Girls' Generation", "SNSD", "소녀시대"], "Super Junior": ["슈퍼주니어"], "BIGBANG": ["Big Bang", "빅뱅"],
    "Wonder Girls": ["원더걸스"], "KARA": ["카라"], "T-ara": ["티아라"], "2NE1": ["투애니원"], "IU": ["아이유"],
    "PSY": ["싸이"], "EXO": ["엑소"], "TWICE": ["트와이스"], "Chanyeol": ["CHANYEOL", "찬열"], "Punch": ["펀치"],
    "Yoon Mi-rae": ["윤미래", "Yoonmirae"], "BTS": ["방탄소년단", "防彈少年團"], "BLACKPINK": ["블랙핑크"],
    "Red Velvet": ["레드벨벳"], "aespa": ["에스파"], "NewJeans": ["뉴진스"], "IVE": ["아이브"],
    "LE SSERAFIM": ["르세라핌"], "Jung Kook": ["정국", "Jungkook"], "ROSÉ": ["Rose", "로제"],
    # 日語
    "坂本九": ["Kyu Sakamoto"], "竹内まりや": ["Mariya Takeuchi"], "X JAPAN": [], "小田和正": ["Kazumasa Oda"],
    "ZARD": [], "DREAMS COME TRUE": [], "高橋洋子": ["Yoko Takahashi"], "スピッツ": ["Spitz"],
    "久保田利伸": ["Toshinobu Kubota"], "安室奈美恵": ["Namie Amuro"], "Kiroro": [], "宇多田ヒカル": ["Hikaru Utada", "Utada Hikaru"],
    "椎名林檎": ["Sheena Ringo", "Ringo Sheena"], "浜崎あゆみ": ["Ayumi Hamasaki"], "夏川りみ": ["Rimi Natsukawa"],
    "中島美嘉": ["Mika Nakashima"], "大塚愛": ["Ai Otsuka"], "平井堅": ["Ken Hirai"], "嵐": ["ARASHI"],
    "GReeeeN": [], "いきものがかり": ["Ikimonogakari"], "RADWIMPS": [], "米津玄師": ["Kenshi Yonezu"],
    "あいみょん": ["Aimyon"], "YOASOBI": [], "LiSA": [], "Official髭男dism": ["Official HIGE DANdism"], "King Gnu": [],
    "Ado": [], "優里": ["Yuuri"], "藤井風": ["Fujii Kaze"], "Aimer": [], "Creepy Nuts": [],
    "韋禮安": ["WeiBird"], "優客李林": ["Ukulele"], "F4": [], "Tank": [], "A-Lin": [],
}

# Variant forms that a plain T->S conversion does not fold together.
VARIANTS = {"裏": "里", "祕": "秘", "癡": "痴", "姊": "姐", "爲": "为", "綫": "线", "峯": "峰",
            "衆": "众", "啓": "启", "羣": "群", "臺": "台", "眞": "真", "歎": "叹", "迴": "回",
            "粧": "妆", "孃": "娘", "着": "着", "週": "周", "游": "游", "麽": "么"}


def main(template, bank_path, out):
    conv = opencc.OpenCC("t2s")
    rows, cat = [], "zh"
    for l in open(bank_path, encoding="utf-8").read().splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        if l.startswith("@"):
            cat = l[1:].strip()
            continue
        rows.append(l + "|" + cat)
    artists = set()
    chars = set()
    for l in rows:
        t, a, y, c = l.split("|")
        int(y)
        assert c in ("zh", "tw", "en", "kr", "jp", "yue", "ot"), l
        for x in a.split("、"):
            artists.add(x)
        chars.update(t + a)
    missing = sorted(a for a in artists if a not in ALIASES and not a.isascii() and not all(ord(ch) < 0x250 for ch in a))
    if missing:
        print("no alias entry:", missing)
    t2s = {}
    for c in sorted(chars):
        s = conv.convert(c)
        if s != c:
            t2s[c] = s
    t2s.update(VARIANTS)
    aliases = {a: ALIASES.get(a, []) for a in sorted(artists)}
    html = open(template, encoding="utf-8").read()
    html = html.replace("/*__BANK__*/", json.dumps("\n".join(rows), ensure_ascii=False))
    html = html.replace("/*__T2S__*/", json.dumps(t2s, ensure_ascii=False))
    html = html.replace("/*__ALIASES__*/", json.dumps(aliases, ensure_ascii=False))
    chorus = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chorus.js"), encoding="utf-8").read()
    html = html.replace("/*__CHORUS__*/", chorus)
    battle = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "battle.js"), encoding="utf-8").read()
    assert html.count("/*__BATTLE__*/") == 1
    html = html.replace("/*__BATTLE__*/", battle)
    assert "/*__" not in html
    open(out, "w", encoding="utf-8").write(html)
    print(f"{len(rows)} songs, {len(artists)} artists, {len(t2s)} char maps -> {out} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main(*sys.argv[1:4])
