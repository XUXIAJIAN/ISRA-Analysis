import csv
import io
import math
import re
import xml.etree.ElementTree as ET


def decode(data):
    for encoding in ('utf-8-sig', 'utf-16', 'gb18030', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeError:
            pass
    raise ValueError('无法识别文件编码')


def number(value):
    n = float(value)
    if not math.isfinite(n):
        raise ValueError('数值不是有限数')
    return n


def parse_csv(data, source):
    records, errors = [], []
    for line, row in enumerate(csv.reader(io.StringIO(decode(data))), 1):
        if not row or not any(row):
            continue
        try:
            if len(row) < 15 or (len(row) - 7) % 8:
                raise ValueError('需要 ISRA 无表头 zone.csv：7 个基本字段及每分区 8 个字段')
            if row[6] not in ('+', '-'):
                raise ValueError('整片判定应为 + 或 -')
            measurements = []
            seen = set()
            for i in range(7, len(row), 8):
                name, status, *values = row[i:i+8]
                if '_' not in name or name in seen or status not in ('+', '-'):
                    raise ValueError('分区名称重复、格式或判定无效')
                seen.add(name)
                v = list(map(number, values))
                measurements.append(dict(zone=name.split('_', 1)[0], item=name, original=status,
                                         maximum=v[0], x=v[1], y=v[2], roc=v[3], roc_x=v[4], roc_y=v[5]))
            records.append(dict(timestamp=row[0], date=row[1], time=row[2], glass=row[3],
                                program=row[4], product=row[5], original=row[6], source=source,
                                line=line, measurements=measurements))
        except (ValueError, IndexError) as e:
            errors.append(f'{source} 第 {line} 行：{e}')
    return records, errors


def parse_rules(data, filename):
    text = decode(data)
    rules = []
    if filename.lower().endswith('.xml'):
        # The supplied export declares utf-16 but contains UTF-8 bytes.
        text = re.sub(r'<\?xml[^>]*\?>', '', text, count=1)
        root = ET.fromstring(text)
        def value(node, tag):
            child = node.find(tag)
            if child is None:
                raise ValueError(f'缺少 {tag}')
            return child.get('name')
        product = value(root.find('Product_info'), 'Program_name')
        for m in root.findall('./Measurements/Measurement'):
            item = value(m, 'Zone_name')
            for metric, prefix in [('maximum', 'Result_maximum'), ('roc', 'ROC')]:
                a, b = number(value(m, prefix+'_limit_A')), number(value(m, prefix+'_limit_B'))
                if a != b:
                    raise ValueError('XML 中 A/B 限值不同，请使用 DFQ 明确上下限，或手动配置；不推测 A/B 含义')
                if a > 0:
                    rules.append(dict(product=product, item=item, metric=metric, lower=-a, upper=a, source=filename))
    elif filename.lower().endswith('.dfq'):
        product = re.search(r'^K1001 (.+)$', text, re.M)
        if not product:
            raise ValueError('DFQ 缺少品种 K1001')
        product = product.group(1).strip()
        fields = {}
        for key, index, val in re.findall(r'^K(\d+)/(\d+) ([^\r\n]*)', text, re.M):
            fields.setdefault(index, {})[key] = val.strip()
        for f in fields.values():
            name = f.get('2002', '')
            if name.endswith(('_Max', '_RoC')):
                item, suffix = name.rsplit('_', 1)
                rules.append(dict(product=product, item=item, metric='maximum' if suffix=='Max' else 'roc',
                                  lower=number(f['2112']), upper=number(f['2113']), source=filename))
    else:
        raise ValueError('公差文件仅支持 XML 或 DFQ')
    return rules


def evaluate(records, rules):
    lookup = {}
    for r in rules:
        key = (r['product'], r['item'], r['metric'])
        lo, hi = number(r['lower']), number(r['upper'])
        if lo > hi:
            raise ValueError('公差下限不能大于上限')
        if key in lookup and lookup[key] != (lo, hi):
            raise ValueError('同一品种、项目、指标存在冲突公差')
        lookup[key] = (lo, hi)
    output = []
    for record in records:
        for m in record['measurements']:
            for metric in ('maximum', 'roc'):
                bounds = lookup.get((record['product'], m['item'], metric))
                # DISTORTION2 RoC zeros are placeholders in the provided export.
                inactive = metric == 'roc' and 'DISTORTION2' in m['item'] and bounds is None
                status = '不适用' if inactive else '未配置' if bounds is None else '合格' if bounds[0] <= m[metric] <= bounds[1] else '超差'
                output.append({**{k:v for k,v in record.items() if k!='measurements'}, **m,
                               'metric':metric, 'value':m[metric], 'status':status,
                               'lower':bounds[0] if bounds else None, 'upper':bounds[1] if bounds else None,
                               'device_zone':m['original'], 'device_glass':record['original']})
    return output


def parse_config_csv(data, source):
    """Read recipe CSV without guessing the semantics of its unnamed limits."""
    rows = list(csv.reader(io.StringIO(decode(data))))
    config, measurement_lines = [], []
    for row in rows:
        if not row or not any(row):
            continue
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}_\d{6}', row[0]):
            measurement_lines.append(row)
        elif row[0] in ('HeatingWires', 'AutoZone'):
            continue
        elif len(row) >= 3 and row[1] in ('A', 'B'):
            config.append(dict(item=row[0], category=row[1], mode=row[2], raw=row[3:], source=source))
        else:
            raise ValueError('无法识别配方配置行：'+row[0])
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerows(measurement_lines)
    records, errors = parse_csv(stream.getvalue().encode(), source)
    products = sorted(set(r['product'] for r in records))
    return records, errors, dict(source=source, products=products, rows=config,
                                warning='原始公差列无表头；须确认两个限值的含义及配方适用日期后，手动建立公差。未自动应用。')


def confirmed_c1ul_rules(config):
    """User confirmed 2026-10-27 recipe: Max then RoC; valid for Nov 3."""
    if config['products'] != ['C1UL WS']:
        raise ValueError('此已确认配方映射仅适用于 C1UL WS')
    grouped = {}
    for row in config['rows']:
        if row['mode'] == 'Off':
            continue
        if row['mode'] != 'RoC' or len(row['raw']) != 4:
            raise ValueError('配方模式或参数格式尚未确认')
        grouped.setdefault(row['item'], []).append(row)
    rules = []
    for item, rows in grouped.items():
        if {r['category'] for r in rows} != {'A', 'B'} or len(rows) != 2 or rows[0]['raw'] != rows[1]['raw']:
            raise ValueError('配方 A/B 配置不同或不完整，不能自动合并')
        raw = rows[0]['raw']
        for metric, flag, value in [('maximum',raw[0],raw[1]),('roc',raw[2],raw[3])]:
            if flag == '0':
                continue
            if flag != '1' or number(value) <= 0:
                raise ValueError('配方启用标志或限值无效')
            limit = number(value)
            rules.append(dict(product='C1UL WS',item=item,metric=metric,lower=-limit,upper=limit,
                              source=config['source']+'（用户确认 Max/RoC 顺序）'))
    return rules
