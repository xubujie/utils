import os
import fnmatch
import argparse
import glob
from tqdm import tqdm


def read_patterns_from_file(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def path_matches_pattern(path, pattern):
    # Normalize separators
    path = path.replace(os.sep, "/")
    pattern = pattern.replace(os.sep, "/")

    # If the pattern is a simple file extension match (e.g., "*.ico")
    if pattern.startswith("*") and "/" not in pattern:
        return fnmatch.fnmatch(os.path.basename(path), pattern)

    # If the pattern ends with '/', append '**' to match all subdirectories and files
    if pattern.endswith("/"):
        pattern += "**"

    # Split the path and pattern into components
    path_parts = path.split("/")
    pattern_parts = pattern.split("/")

    # Use fnmatch for each component
    i = 0
    for pattern_part in pattern_parts:
        if pattern_part == "**":
            # Match any number of path components
            if i == len(pattern_parts) - 1:
                return True  # '**' at the end matches everything
            for j in range(i, len(path_parts)):
                if path_matches_pattern(
                    "/".join(path_parts[j:]), "/".join(pattern_parts[i + 1 :])
                ):
                    return True
            return False
        elif i >= len(path_parts):
            return False
        elif not fnmatch.fnmatch(path_parts[i], pattern_part):
            return False
        i += 1

    # If we've matched all parts of the pattern, it's a match if we've also used all parts of the path
    return i == len(path_parts)


def should_include_path(path, ignore_patterns, whitelist_patterns):
    # Normalize path separators
    path = path.replace(os.sep, "/")

    # Check if the path matches any ignore pattern
    if any(path_matches_pattern(path, pattern) for pattern in ignore_patterns):
        return False

    # Check if the path matches any whitelist pattern
    if whitelist_patterns:
        return any(
            path_matches_pattern(path, pattern) for pattern in whitelist_patterns
        )

    return True


def count_files(repo_path, ignore_patterns, whitelist_patterns):
    count = 0
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [
            d
            for d in dirs
            if should_include_path(
                os.path.join(root, d), ignore_patterns, whitelist_patterns
            )
        ]
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), repo_path)
            if should_include_path(file_path, ignore_patterns, whitelist_patterns):
                count += 1
    return count


def process_repository(repo_path, output_file, ignore_patterns, whitelist_patterns):
    total_files = count_files(repo_path, ignore_patterns, whitelist_patterns)

    with open(output_file, "w", encoding="utf-8") as outfile:
        with tqdm(total=total_files, desc="Processing files", unit="file") as pbar:
            for root, dirs, files in os.walk(repo_path):
                # Filter out ignored directories
                dirs[:] = [
                    d
                    for d in dirs
                    if should_include_path(
                        os.path.join(root, d), ignore_patterns, whitelist_patterns
                    )
                ]

                for file in files:
                    file_path = os.path.relpath(os.path.join(root, file), repo_path)

                    if should_include_path(
                        file_path, ignore_patterns, whitelist_patterns
                    ):
                        try:
                            full_path = os.path.join(root, file)
                            with open(full_path, "r", encoding="utf-8") as infile:
                                content = infile.read()

                            outfile.write(f"{file_path}\n")
                            outfile.write("=" * 20 + "\n")
                            outfile.write(content)
                            outfile.write("\n" + "=" * 20 + "\n\n")
                        except Exception as e:
                            print(f"Error processing file {file_path}: {str(e)}")
                        finally:
                            pbar.update(1)


def expand_patterns(patterns, repo_path):
    expanded = []
    for pattern in patterns:
        if "*" in pattern or "?" in pattern or "[" in pattern:
            # This is a glob pattern
            for matched_path in glob.glob(
                os.path.join(repo_path, pattern), recursive=True
            ):
                expanded.append(
                    os.path.relpath(matched_path, repo_path).replace(os.sep, "/")
                )
        else:
            # This is a literal path
            expanded.append(pattern.replace(os.sep, "/"))
    return expanded


def main():
    parser = argparse.ArgumentParser(
        description="Convert a local repository to a single file for LLM context."
    )
    parser.add_argument("--repo_path", help="Path to the local repository", default=".")
    parser.add_argument(
        "--output_file", help="Path to the output file", default="repo_contents.txt"
    )
    parser.add_argument(
        "--ignore-file",
        help="Path to a file containing ignore patterns",
        default=".il",
    )
    parser.add_argument(
        "--whitelist-file",
        help="Path to a file containing whitelist patterns",
        default=".whitelist",
    )

    args = parser.parse_args()
    ignore_patterns = []
    whitelist_patterns = []
    ignore_patterns.extend(read_patterns_from_file(args.ignore_file))
    whitelist_patterns.extend(read_patterns_from_file(args.whitelist_file))

    # Expand glob patterns
    ignore_patterns = expand_patterns(ignore_patterns, args.repo_path)
    whitelist_patterns = expand_patterns(whitelist_patterns, args.repo_path)

    process_repository(
        args.repo_path, args.output_file, ignore_patterns, whitelist_patterns
    )
    print(f"\nRepository contents have been written to {args.output_file}")


if __name__ == "__main__":
    main()
