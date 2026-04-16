from pathlib import Path

from idr_analysis import build_idr_outputs


PAPER_OUTPUT = Path("./data/idr_papers.csv")
PEOPLE_OUTPUT = Path("./data/idr_people.csv")
COMMUNITY_OUTPUT = Path("./data/idr_communities.csv")


def write_fresh_csv(df, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
        print(f"Deleted existing output file: {output_path}")
    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df):,} rows to {output_path}")


def main() -> None:
    outputs = build_idr_outputs()
    write_fresh_csv(outputs["paper_idr_df"], PAPER_OUTPUT)
    write_fresh_csv(outputs["people_idr_df"], PEOPLE_OUTPUT)
    write_fresh_csv(outputs["community_idr_df"], COMMUNITY_OUTPUT)


if __name__ == "__main__":
    main()
