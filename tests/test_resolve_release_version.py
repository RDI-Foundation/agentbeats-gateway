import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "resolve-release-version.sh"
)
MANAGED_TAG_MARKER = "managed-by=agentbeats-gateway-ci"
IMAGE_REF = "ghcr.io/example/agentbeats-gateway"


def run(cmd: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def parse_github_output(output: str) -> dict[str, str | list[str]]:
    parsed: dict[str, str | list[str]] = {}
    lines = iter(output.splitlines())

    for line in lines:
        if "<<" in line:
            key, marker = line.split("<<", 1)
            values = []
            for value in lines:
                if value == marker:
                    break
                values.append(value)
            parsed[key] = values
            continue

        key, value = line.split("=", 1)
        parsed[key] = value

    return parsed


class ResolveReleaseVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        self.commit_index = 0

        run(["git", "init", "-q"], self.repo)
        run(["git", "config", "user.name", "Test User"], self.repo)
        run(["git", "config", "user.email", "test@example.com"], self.repo)
        run(["git", "config", "commit.gpgsign", "false"], self.repo)
        run(["git", "config", "tag.gpgsign", "false"], self.repo)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def commit(self, message: str) -> None:
        self.commit_index += 1
        (self.repo / "state.txt").write_text(
            f"{self.commit_index}:{message}\n",
            encoding="utf-8",
        )
        run(["git", "add", "state.txt"], self.repo)
        run(["git", "commit", "-qm", message], self.repo)

    def tag_lightweight(self, name: str, ref: str = "HEAD") -> None:
        run(["git", "tag", name, ref], self.repo)

    def tag_managed(self, name: str, ref: str = "HEAD") -> None:
        run(
            [
                "git",
                "tag",
                "-a",
                name,
                "-m",
                f"Release {name}",
                "-m",
                MANAGED_TAG_MARKER,
                ref,
            ],
            self.repo,
        )

    def resolve(self, series: str) -> dict[str, str | list[str]]:
        (self.repo / "version-series.txt").write_text(f"{series}\n", encoding="utf-8")
        output = run(
            [
                "bash",
                str(SCRIPT),
                "version-series.txt",
                IMAGE_REF,
            ],
            self.repo,
        )
        return parse_github_output(output)

    def test_major_zero_series_only_emits_minor_floating_tag(self) -> None:
        self.commit("initial")

        resolved = self.resolve("0.3.x")

        self.assertEqual(resolved["version"], "0.3.0")
        self.assertEqual(resolved["version_tag"], "v0.3.0")
        self.assertEqual(resolved["floating_tags"], "v0.3")
        self.assertEqual(resolved["git_tags"], ["v0.3.0", "v0.3"])
        self.assertEqual(
            resolved["image_tags"],
            [f"{IMAGE_REF}:v0.3.0", f"{IMAGE_REF}:v0.3"],
        )

    def test_manual_tags_do_not_drive_the_version_sequence(self) -> None:
        self.commit("first release")
        self.tag_managed("v0.3.0")
        self.tag_lightweight("v0.3.99")

        self.commit("next release")

        resolved = self.resolve("0.3.x")

        self.assertEqual(resolved["version_tag"], "v0.3.1")
        self.assertEqual(resolved["floating_tags"], "v0.3")

    def test_existing_managed_head_tag_is_reused_on_rerun(self) -> None:
        self.commit("release 1.2.2")
        self.tag_managed("v1.2.2")
        self.commit("release 1.2.3")
        self.tag_managed("v1.2.3")

        resolved = self.resolve("1.2.x")

        self.assertEqual(resolved["version_tag"], "v1.2.3")
        self.assertEqual(resolved["floating_tags"], "v1,v1.2")
        self.assertEqual(resolved["git_tags"], ["v1.2.3", "v1", "v1.2"])

    def test_prerelease_series_uses_semver_style_floating_tag(self) -> None:
        self.commit("beta 0")
        self.tag_managed("v1.2.3-beta.0")
        self.commit("beta 1")

        resolved = self.resolve("1.2.3-beta.x")

        self.assertEqual(resolved["version_tag"], "v1.2.3-beta.1")
        self.assertEqual(resolved["floating_tags"], "v1.2.3-beta")
        self.assertEqual(
            resolved["image_tags"],
            [f"{IMAGE_REF}:v1.2.3-beta.1", f"{IMAGE_REF}:v1.2.3-beta"],
        )


if __name__ == "__main__":
    unittest.main()
