import re
import os
import sys
from pathlib import Path


def parse_filename(filename: str) -> dict | None:
    """
    Parse filenames like:
      Chapter 1482. Sao tự nhiên hắn lại xuất hiện ở đây (2).txt
      Chapter 1491. Không cần làm vậy đâu. (1).txt
      Chapter 1508. Nói thì ai mà không nói được.txt        <- no part number
      Chapter 1514. Trên đời này chuyện gì cũng xảy ra(3).txt
      Chapter 1516 Chuyện này đâu phải lỗi của ta(1).txt   <- no dot after number
    """
    pattern = r'^Chapter\s+(\d+)[.\s]+(.+?)(?:\s*\((\d+)\))?\.txt$'
    m = re.match(pattern, filename.strip(), re.IGNORECASE)
    if not m:
        return None

    title = m.group(2).strip().rstrip('.')
    part_num = int(m.group(3)) if m.group(3) else None

    return {
        'chapter_num': int(m.group(1)),
        'part_num': part_num,
        'title': title,
        'filename': filename,
    }


def group_files(parsed_files: list) -> list:
    """
    Group consecutive parts into combined chapters.
    Rules:
      - part_num == 1 starts a new group
      - part_num == None means standalone file -> its own group
    """
    groups = []
    current_group = []

    for entry in parsed_files:
        part = entry['part_num']

        if part is None:
            if current_group:
                groups.append(current_group)
                current_group = []
            groups.append([entry])
        elif part == 1:
            if current_group:
                groups.append(current_group)
            current_group = [entry]
        else:
            current_group.append(entry)

    if current_group:
        groups.append(current_group)

    return groups


def make_output_filename(group: list) -> str:
    first = group[0]
    last = group[-1]
    title = first['title']

    if first['chapter_num'] == last['chapter_num']:
        prefix = f"Chapter {first['chapter_num']}"
    else:
        prefix = f"Chapter {first['chapter_num']} - {last['chapter_num']}"

    return f"{prefix}. {title}.txt"


def combine_group(group: list, source_dir) -> str:
    separator = '\n\n\n'
    parts = []
    for entry in group:
        filepath = source_dir / entry['filename']
        content = filepath.read_text(encoding='utf-8').strip()
        parts.append(content)
    return separator.join(parts)


def main():
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir / 'wattpad_chapters'
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else script_dir / 'wattpad_combined'

    if not source_dir.is_dir():
        print(f"Error: source directory '{source_dir}' not found")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    all_files = sorted(f.name for f in source_dir.glob('*.txt'))
    parsed = []
    skipped = []

    for fname in all_files:
        result = parse_filename(fname)
        if result:
            parsed.append(result)
        else:
            skipped.append(fname)

    if skipped:
        print(f"[warning] Could not parse {len(skipped)} file(s):")
        for f in skipped:
            print(f"  - {f}")

    if not parsed:
        print("No valid chapter files found.")
        sys.exit(0)

    parsed.sort(key=lambda x: (x['chapter_num'], x['part_num'] or 0))
    groups = group_files(parsed)

    print(f"\nFound {len(parsed)} file(s) -> {len(groups)} combined chapter(s)\n")

    for group in groups:
        out_filename = make_output_filename(group)
        out_path = output_dir / out_filename
        combined_content = combine_group(group, source_dir)
        out_path.write_text(combined_content, encoding='utf-8')

        chapter_nums = [str(e['chapter_num']) for e in group]
        parts_label = ', '.join(
            str(e['part_num']) if e['part_num'] else 'standalone'
            for e in group
        )
        print(f"[created] {out_filename}")
        print(f"          chapters: {', '.join(chapter_nums)} | parts: {parts_label}")

    print(f"\nDone. Output saved to: {output_dir}")


if __name__ == '__main__':
    main()