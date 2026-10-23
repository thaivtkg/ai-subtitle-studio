# -*- coding: utf-8 -*-
"""Static stopword dictionaries, boundary filters, and suffix guards for glossary extraction."""

# 1. Từ dừng ranh giới (Biên trước / sau của cụm từ danh từ riêng)
_BOUNDARY_STOPWORDS = {
    "video", "trong", "ngoài", "trên", "dưới", "giữa", "cùng", "với", "của", "cho",
    "tại", "từ", "đến", "tới", "về", "khi", "nếu", "vì", "do", "bởi", "để", "nhưng",
    "hoặc", "và", "hay", "các", "những", "một", "này", "đó", "chuyến", "cuộc", "buổi",
    "gặp", "đi", "the", "an", "this", "that", "these", "those", "in", "on", "at",
    "to", "for", "with", "from", "by", "about", "into", "through", "after", "before",
    "between", "under", "over", "how", "what", "why", "when", "where", "who", "it",
    "he", "she", "we", "you", "they", "let", "there", "here", "and", "or", "but",
    # Số từ & lượng từ tiếng Việt (không bao gồm tên riêng phổ biến)
    "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười",
    "trăm", "nghìn", "vạn", "đôi", "vài", "mỗi", "từng", "mọi", "nhiều", "ít",
    # Từ phương vị & vị trí
    "bề", "mặt", "phía", "bên", "trước", "sau", "đầu", "cuối",
}

# 2. Cụm từ dừng đa từ (Multi-word stop phrases - Tiếng Việt)
_MULTIWORD_STOP_PHRASES = {
    "anh hùng", "anh em", "anh trai", "anh chàng", "dũng sĩ", "quái vật",
    "quái nhân", "yêu quái", "yêu ma", "ác ma", "ác quỷ", "ma vương",
    "ma vật", "nội dung", "hướng dẫn", "giới thiệu", "tóm tắt", "bảo vệ",
    "tiêu diệt", "giải cứu", "người dân", "dân làng", "bá tánh", "thảo dân",
    "chương trình", "chiến đấu", "chiến binh", "hiệp sĩ", "lập trình",
    "quản lý", "giải thích", "khám phá", "vùng đất", "trận chiến", "bộ nhớ",
    "nữ sinh", "nam sinh", "học sinh", "sinh viên", "thiếu nữ", "cô gái",
    "cô bé", "cậu bé", "chàng trai", "thành phố", "đô thị", "hiện đại",
    "thời đại", "siêu nhân", "siêu anh", "siêu anh hùng", "phép thuật",
    "thẻ bài", "thu phục", "biến hình", "phong ấn", "thế giới", "dị giới",
    "cổ trang", "tiên hiệp", "kiếm hiệp", "nhân vật", "câu chuyện", "bộ phim",
    "tập phim", "trò chơi", "bề ngoài", "bốn người", "bốn năm",
    "đôi bạn", "đôi bên", "anh ta", "cô ta", "chúng ta", "chúng tôi",
    "hôm nay", "ngày mai", "hôm qua",
    # AC-GLOSS-03: Mở rộng Stopwords tiếng Việt
    "thành viên", "đội trưởng", "nhóm trưởng", "trưởng nhóm", "sự kiện",
    "hệ thống", "dữ liệu", "mùa phim", "huấn luyện", "bài học", "kỹ năng",
    "anh ấy", "cô ấy", "chị ấy", "em ấy",
}

# 3. Từ dừng Latin / Tiếng Anh đơn lẻ
_LATIN_STOPWORDS = _BOUNDARY_STOPWORDS | {
    "hướng", "dẫn", "giới", "thiệu", "tóm", "tắt", "phần", "bài", "chương",
    "cách", "trận", "khám", "phá", "vùng", "đất", "lập", "trình", "quản",
    "bộ", "nhớ", "giải", "quái", "vật", "yêu", "ma", "người", "dân", "làng",
    "tiêu", "diệt", "vệ", "cứu", "bạn", "tôi", "ta", "ngươi", "viên", "nữ",
    "học", "sinh", "thiếu", "cô", "siêu", "phố", "hiện", "thẻ", "phép",
    "thuật", "overview", "summary", "introduction", "tutorial", "guide",
    "episode", "part", "chapter", "don", "doesn", "didn", "won", "can",
    "isn", "aren", "wasn", "weren",
    # Đại từ xưng hô đơn độc
    "anh", "chị", "em", "chú", "bác", "họ", "chúng", "nó", "hắn",
    # AC-GLOSS-03: Bổ sung Stopword Latin/English
    "member", "team", "leader", "support", "item", "event", "system",
    "data", "file", "online", "offline", "user", "anime", "game",
    "series", "season", "battle", "fight",
}

# 4. Từ dừng CJK (Tiếng Nhật, Hàn, Hán tự phổ thông)
_CJK_STOPWORDS = {
    # 4.1. Hệ thống & Meta
    "動画", "解説", "紹介", "説明", "今回", "内容", "違い", "方法", "場合", "使用", "利用", "基本", "概要",
    "동영상", "설명", "소개", "영상", "내용", "이번", "방법", "사용",
    # 4.2. Số đếm & Lượng từ & Thời gian
    "一人", "二人", "三人", "四人", "五人", "年後", "日前", "年前", "時間", "分間", "秒間",
    "時期", "日常", "最初", "最後", "週間", "月間",
    # 4.3. Liên từ, phó từ, trạng từ
    "一方", "日々", "徐々", "如何", "単独", "結局", "突然", "最近", "現在", "過去", "未来",
    "絶対", "決意", "予想外", "違和感",
    # 4.4. Gốc động từ / tính từ cụt đuôi (Do cắt đuôi Hiragana)
    "経験浅", "調子者", "力尽", "出会", "裏切", "仕掛", "目立", "暗躍", "魅了", "変貌", "支配", "壊滅",
    # 4.5. Katakana thông thường (Generic Loanwords)
    # Văn hóa / Hoạt động
    "アニメ", "マンガ", "ゲーム", "シリーズ", "シーズン", "エピソード", "イベント",
    "バトル", "ファイト", "レッスン", "トレーニング", "ファン", "サービス",
    # Tổ chức / Nhân sự
    "メンバー", "チーム", "リーダー", "サポート", "パートナー", "グループ", "クラブ", "ユーザー", "スタッフ",
    # Kỹ thuật / Đời sống
    "システム", "データ", "ファイル", "オンライン", "オフライン", "リアル", "ネット",
    "レベル", "スキル", "アイテム", "ショップ", "カフェ", "ホテル", "ドレス", "ダメージ",
    "ガス", "ピンチ", "ギャング", "カウンセリング", "コンプレックス",
    # 4.6. Danh từ trừu tượng / Hoạt cảnh chung
    "頭脳", "友達", "少女", "生徒", "教官", "着任", "美貌", "心理", "担当", "歓迎",
    "成績優秀", "人気者", "手先", "原因", "隙間", "配下", "邪魔", "世界", "宇宙", "人格",
    "組織", "指令", "状況", "自由", "危険", "判断", "敗北", "精神", "復讐", "忠告",
    "再戦", "劣勢", "機転", "悪事", "攻撃", "運命", "究極", "覚醒", "異変", "乱入",
    "正義", "戦隊", "養成学校", "親友", "彼女", "自分", "相手", "影響", "事態", "強大",
    "絶望的", "精神的", "暗黒", "転生", "封印", "暴走", "復活", "日々力",
}

# 5. Hậu tố định tính/ngữ pháp Kanji cần loại bỏ khi không nằm trong ngoặc 「」
_KANJI_SUFFIX_BLACKLIST = ("的", "性", "化", "感", "界", "力", "視", "法", "論", "風")

# Ngoại lệ danh từ chuyên ngành / huyền huyễn kết thúc bằng hậu tố trên
_KANJI_SUFFIX_WHITELIST = {
    "魔力", "妖力", "霊力", "重力", "超能力", "法力", "武力", "異世界", "魔界",
}
