"""
从 rocoworldwiki.com 批量抓取技能数据
输出 CSV: 技能名, 属性, 分类, 耗能, 威力, 技能描述, 可学习精灵列表
"""
import subprocess
import json
import csv
import time
import sys
import urllib.parse

OUTPUT_CSV = "data/skills_wiki.csv"

# All 465 skill names (extracted from the wiki)
SKILL_NAMES = ["操控","乘胜追击","冲撞","触底强击","穿膛","垂死反击","伺机而动","打鼾","当头棒喝","吨位压制","防反","防御","飞踢","复写","攻击场地","鼓劲","聒噪","后发制人","荟萃","彗星","激怒","棘刺","加固","见招拆招","践踏","借用","精神扰乱","快速移动","力量增效","连续爪击","乱打","落星","埋伏","猛烈撞击","魔法增效","魔能爆","能量炮","能量刃","逆袭","拍击","咆哮","迫近攻击","气势一击","倾泻","取念","热身运动","锐利眼神","三鼓作气","扫尾","晒太阳","嗜痛","天旋地转","偷袭","突袭","退化","吞噬","无畏之心","吓退","先发制人","消毒法","星星撞击","休息回复","许愿星","蓄能轰击","旋转突击","血气","压扁","湮灭","摇篮曲","耀眼","以重制重","音爆","音波弹","应激反应","有效预防","指指点点","重击","抓挠","追打","阻断","孢子爆散","抽枝","顶端优势","芳香诱引","飞叶","丰饶","富养化","根吸收","光合作用","光能聚集","花炮","花香","汲取","棘突","寄生种子","荆棘爪","聚盐","蜡质膜","酶浓度调整","筛管奔流","盛开","藤鞭","藤绞","徒长","仙人掌刺击","纤维化","氧输送","叶绿光束","移花接木","种皮爆裂","种子弹","爆裂飞弹","持续高温","充分燃烧","吹火","淬火","焚毁","高温回火","火苗","火焰冲锋","火焰护盾","火焰箭","火焰切割","火云车","火爪","烈焰风暴","流火","流星火雨","怒火","燃尽","热气","热身","山火","闪燃","双响炮","天火","炎爆术","炎打","炎枪","炎息","易燃物质","引燃","炙热波动","灼伤","潮汐","潮涌","肥皂泡","激流","泡沫","泡沫幻影","气泡","求雨","润泽","湿润印记","甩水","水波术","水弹","水弹枪","水光冲击","水花四溅","水环","水幕冲击","水泡盾","水炮","水刃","天洪","洗礼","蓄水","盐水浴","涌泉","放晴","光球","光刃","光之矛","过曝","虹光冲击","镜像反射","脉冲光线","漫反射","闪光","闪光冲击","天光","透射","折射","折线冲击","壁垒","不动如山","刺盾","地刺","地陷","地震","遁地","跺地","钧势","裂石","流沙","落石","鸣沙陷阱","泥巴喷射","泥浆","泥浆铠甲","泥沼","抛石","热砂","沙涌","石肤术","石锁","岩脉崩毁","岩土暴击","扬沙","硬化","淤泥表皮","陨石","震击","暴风雪","冰雹","冰刺","冰点","冰冻光线","冰锋横扫","冰荆棘","冰捆缚","冰墙","冰天雪地","冰爪","冰锥","打雪仗","冬至","堆雪人","风吹雪","缓冻","极寒领域","极速冷冻","冷风","霜冻","霜降","霜天","速冻","碎冰冰","碎冰击","雾气环绕","雪球","雪替身","吹炎","架势","角击","龙吼","龙炮","龙威","龙息环爆","龙血","龙爪","龙之利爪","龙之舞","绵里藏针","升龙咆哮","隼鳞","怨力打击","超导","超导加速","触电","磁干扰","导电撞击","电磁偏转","电弧","电离爆破","电流","感电","过载回路","集中","加大功率","交叉闪电","雷暴","离子火花","落雷","麻痹","强制重启","球状闪电","闪击折返","引雷","远程访问","增程电池","不可接触","毒孢子","毒囊","毒泡泡","毒雾","毒液渗透","毒沼","毒针","腐化","感染病","剧毒","溃烂触碰","连续毒针","落井下毒","溶解液","以毒攻毒","疫病吐息","瘴气喷射","鸩毒","翅刃","虫刺","虫蛊","虫击","虫茧","虫结阵","虫鸣","虫群","虫群过境","虫群智慧","虫网","飞断","假寐","啃咬","捆缚","食腐","噬心","网缚","尾后针","掩护","蛰针","贮藏","爆冲","崩拳","缠丝劲","寸拳","叠势","反击拳","防御反击","贯手","化劲","技巧打击","截拳","破防","破绽","气波","气沉丹田","散手","提气","听桥","无影脚","一拳","影袭","硬门","预备势","斩断","暴风眼","乘风","风起","风墙","风矢","风隐","俯冲猛击","回旋风暴","疾风刺","疾风连袭","龙卷风","鸣叫","闪击","扇风","翼击","鹰爪","羽化加速","羽毛舞","羽刃","羽翼庇护","啄击","爆米花爆破","鞭打","超级糖果","赤子之心","飞吻","魅惑","逆向演化","捧杀","碰爪","柔弱","撒娇","砂糖弹球","生日蛋糕","示弱","玩具乐园","幼态延续","月光合奏","报复","背袭","嘲弄","恶作剧","坟场搏击","诡刺","鬼火","幻象","降灵","惊吓盒子","恐吓","灵光","灵媒","午夜噪音","小偷小摸","虚化","幽灵爆发","暗突袭","暗箱操作","彼岸之手","蝙蝠","趁火打劫","冲击","等价交换","跌落","恶能量","恶念交换","恶意逃离","横纵斩","极限撕裂","力量吞噬","掠夺","魔爪","骗局","迫害","欺诈契约","牵连","撕裂","撕咬","贪婪","伪造账单","虚假破产","隐藏条款","灾厄","栽赃","拆卸","齿轮扭矩","齿轮切开","传感器","磁暴","杠杆置换","钢铁洪流","钢钻","金属噪音","离子震荡","联动装置","能量守恒","啮合传递","械斗","轴承支撑","主轴","超维投射","超新星馈赠","错乱","大爆炸","多维击打","二律背反","空间压迫","粒子对撞","冥想","念力膨胀","双星","四维降解","坍缩","偷师","心灵洞悉","星轨裂变","星链","针状物","星云漩涡"]


def run_browser(cmd):
    """Run an agent-browser command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def scrape_skill(name):
    """Navigate to skill detail page and extract data."""
    encoded = urllib.parse.quote(name)
    url = f"https://www.rocoworldwiki.com/wiki/skill/{encoded}"

    run_browser(f'agent-browser open "{url}"')
    run_browser('agent-browser wait --load networkidle')
    time.sleep(1)  # Extra wait for Vue rendering

    # Extract data via JS
    js = """
var result = {};
// Get all text content
var body = document.body.innerText;

// Parse structured fields
var fields = ['属性', '分类', '耗能', '威力'];
fields.forEach(function(f) {
    var regex = new RegExp(f + '\\\\n([^\\\\n]+)');
    var m = body.match(regex);
    if (m) result[f] = m[1].trim();
});

// Get skill description
var descMatch = body.match(/技能效果\\n\\n([\\s\\S]*?)\\n\\n图鉴编号/);
if (descMatch) result['描述'] = descMatch[1].trim();
else {
    descMatch = body.match(/技能效果\\n\\n([\\s\\S]*?)\\n\\n/);
    if (descMatch) result['描述'] = descMatch[1].trim();
}

// Get learnable pets
var petSection = body.split('可以学会的精灵');
if (petSection.length > 1) {
    var petText = petSection[petSection.length - 1];
    var lines = petText.split('\\n').filter(function(l) { return l.trim().length > 0; });
    // Skip first line (count like "25 只")
    var pets = [];
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.match(/^\\d+ 只$/)) continue;
        if (line.match(/^COMPATIBLE/)) continue;
        if (line.length > 0 && line.length < 30) pets.push(line);
    }
    result['精灵'] = pets;
} else {
    result['精灵'] = [];
}

JSON.stringify(result);
"""
    raw = run_browser(f"agent-browser eval --stdin <<'EVALEOF'\n{js}\nEVALEOF")

    try:
        # The output may have the checkmark prefix, find the JSON part
        for line in raw.split('\n'):
            line = line.strip()
            if line.startswith('"') or line.startswith('{'):
                data = json.loads(line)
                if isinstance(data, str):
                    data = json.loads(data)
                return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def main():
    total = len(SKILL_NAMES)
    results = []
    failed = []

    print(f"Starting scrape of {total} skills...")

    for i, name in enumerate(SKILL_NAMES):
        print(f"[{i+1}/{total}] {name}...", end=" ", flush=True)
        try:
            data = scrape_skill(name)
            if data and '描述' in data:
                pets = "|".join(data.get('精灵', []))
                row = {
                    '技能名': name,
                    '属性': data.get('属性', ''),
                    '分类': data.get('分类', ''),
                    '耗能': data.get('耗能', ''),
                    '威力': data.get('威力', ''),
                    '技能描述': data.get('描述', ''),
                    '可学习精灵': pets,
                }
                results.append(row)
                print(f"OK ({len(data.get('精灵', []))} pets)")
            else:
                print(f"INCOMPLETE: {data}")
                failed.append(name)
        except Exception as e:
            print(f"ERROR: {e}")
            failed.append(name)

        # Save progress every 50 skills
        if (i + 1) % 50 == 0 or i == total - 1:
            _write_csv(results)
            print(f"  >> Saved {len(results)} skills to {OUTPUT_CSV}")

    print(f"\nDone! {len(results)} success, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")


def _write_csv(results):
    if not results:
        return
    fieldnames = ['技能名', '属性', '分类', '耗能', '威力', '技能描述', '可学习精灵']
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


if __name__ == '__main__':
    main()
