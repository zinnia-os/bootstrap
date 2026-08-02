#!/usr/bin/env python3
import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def root_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def want_kvm(arch: str, mode: str) -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False
    return arch == platform.machine() and os.access("/dev/kvm", os.R_OK | os.W_OK)


def build_command(args: argparse.Namespace) -> list[str]:
    arch = args.arch
    qemu = f"qemu-system-{arch}"
    if shutil.which(qemu) is None:
        sys.exit(f"vm-util: {qemu} not found in PATH")

    build_dir = ROOT / f"build-{arch}"
    image = Path(args.image) if args.image else build_dir / "zinnia.img"
    ovmf = ROOT / "ovmf" / f"ovmf-code-{arch}.fd"

    cmd = [qemu, "-m", args.mem, "-smp", str(args.smp), "-no-reboot", "-no-shutdown"]

    if want_kvm(arch, args.kvm):
        cmd += ["-cpu", "host,migratable=off", "-accel", "kvm"]
    else:
        if args.pci:
            sys.exit(
                "vm-util: PCI passthrough requires KVM (use --kvm on); "
                "/dev/kvm is unavailable"
            )
        cmd += ["-cpu", "max", "-accel", "tcg"]

    if not ovmf.exists():
        sys.exit(
            f"vm-util: missing firmware {root_relative(ovmf)} "
            f"(run ./tasks/get-ovmf.sh {arch})"
        )
    cmd += ["-drive", f"if=pflash,unit=0,format=raw,file={ovmf},readonly=on"]

    headless = args.headless or args.display == "none"
    if args.gl and headless:
        sys.exit("vm-util: --gl requires a graphical display backend")

    if headless:
        cmd += ["-display", "none"]
    else:
        gl = ",gl=on" if args.gl else ""
        cmd += ["-display", f"{args.display},zoom-to-fit=off{gl}"]
    if args.serial != "none":
        cmd += ["-serial", args.serial]

    if arch == "x86_64":
        cmd += ["-machine", "q35,smm=off", "-rtc", "base=localtime,clock=host"]
        if not headless:
            cmd += ["-device", "virtio-vga-gl" if args.gl else "virtio-vga"]
    elif arch == "riscv64" or arch == "aarch64":
        machine = "virt,acpi=off" + (",gic-version=3" if arch == "aarch64" else "")
        cmd += [
            "-machine",
            machine,
            "-device",
            "ramfb",
            "-device",
            "virtio-gpu-gl-pci" if args.gl else "virtio-gpu-pci",
        ]

    if not args.no_usb_input:
        pointer = "usb-mouse" if args.pointer == "mouse" else "usb-tablet"
        cmd += [
            "-device",
            "qemu-xhci,id=input-xhci",
            "-device",
            "usb-hub,bus=input-xhci.0,port=1",
            "-device",
            "usb-kbd,bus=input-xhci.0,port=1.1",
            "-device",
            "usb-hub,bus=input-xhci.0,port=2",
            "-device",
            f"{pointer},bus=input-xhci.0,port=2.1",
        ]

    live = None
    if args.live is not None:
        live = Path(args.live) if args.live else build_dir / "zinnia-live.img"
        if not live.exists():
            sys.exit(
                f"vm-util: missing live image {root_relative(live)} (run 'make live')"
            )
        cmd += [
            "-device",
            "qemu-xhci,id=live-xhci",
            "-drive",
            f"format=raw,file={live},if=none,id=live",
            "-device",
            "usb-storage,bus=live-xhci.0,drive=live,bootindex=1",
        ]
        if not image.exists():
            image.parent.mkdir(parents=True, exist_ok=True)
            with open(image, "wb") as f:
                f.truncate(args.target_size)
            print(
                f"vm-util: created blank install target {root_relative(image)}",
                file=sys.stderr,
            )

    if not image.exists() and live is None:
        sys.exit(
            f"vm-util: missing disk image {root_relative(image)} "
            f"(build it per the README) or pass --live"
        )
    if image.exists():
        bootindex = "2" if live is not None else "1"
        cmd += ["-drive", f"format=raw,file={image},if=none,id=disk"]
        if args.disk == "virtio-blk":
            cmd += ["-device", f"virtio-blk-pci,drive=disk,bootindex={bootindex}"]
        else:
            cmd += [
                "-device",
                f"nvme,serial=FAKE_SERIAL_ID,drive=disk,bootindex={bootindex}",
            ]

    if args.nic != "none":
        cmd += [
            "-netdev",
            "user,id=net0,hostfwd=tcp::10022-:22",
            "-device",
            f"{args.nic},netdev=net0",
        ]

    for bdf in args.pci:
        cmd += ["-device", f"vfio-pci,host={bdf}"]

    cmd += args.extra
    return cmd


def cmd_run(args: argparse.Namespace) -> int:
    cmd = build_command(args)
    printable = " ".join(shlex.quote(c) for c in cmd)
    if args.dry_run:
        print(printable)
        return 0
    print(f"+ {printable}", file=sys.stderr)
    return subprocess.run(cmd).returncode


def main() -> int:
    parser = argparse.ArgumentParser(prog="vm-util", description="QEMU util")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="launch QEMU (default)")
    run.add_argument(
        "--arch", default="x86_64", choices=["x86_64", "riscv64", "aarch64"]
    )
    run.add_argument("--image", help="disk image (default build-<arch>/zinnia.img)")
    run.add_argument(
        "--disk",
        choices=["nvme", "virtio-blk"],
        default="nvme",
        help="disk controller model (default nvme)",
    )
    run.add_argument(
        "--live",
        nargs="?",
        const="",
        help="boot the live installation medium as a USB disk "
        "(default build-<arch>/zinnia-live.img); the regular image "
        "becomes a blank install target",
    )
    run.add_argument(
        "--target-size",
        type=lambda v: int(v) * 1024 * 1024,
        default=4096 * 1024 * 1024,
        metavar="MIB",
        help="size of the install target created for --live (default 4096)",
    )
    run.add_argument("--smp", type=int, default=4, help="vCPU count (default 4)")
    run.add_argument("--mem", default="2G", help="guest memory (default 2G)")
    run.add_argument(
        "--kvm",
        choices=["auto", "on", "off"],
        default="auto",
        help="KVM acceleration (default auto)",
    )
    run.add_argument(
        "--display", default="gtk", help="QEMU display backend, or 'none' (default gtk)"
    )
    run.add_argument(
        "--headless", action="store_true", help="shorthand for --display none"
    )
    run.add_argument(
        "--gl",
        action="store_true",
        help="use the virglrenderer-backed virtio-gpu and enable host GL",
    )
    run.add_argument(
        "--serial",
        default="stdio",
        help="QEMU -serial backend, or 'none' (default stdio)",
    )
    run.add_argument(
        "--nic",
        default="virtio-net-pci",
        metavar="MODEL",
    )
    run.add_argument(
        "--pci",
        action="append",
        default=[],
        metavar="BDF",
    )
    run.add_argument(
        "--no-usb-input",
        action="store_true",
    )
    run.add_argument(
        "--pointer",
        default="tablet",
        choices=["tablet", "mouse"],
    )
    run.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
    )
    run.add_argument(
        "extra", nargs="*", help="extra args passed verbatim to QEMU (after --)"
    )
    run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    if args.command is None:
        args = parser.parse_args(["run"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
