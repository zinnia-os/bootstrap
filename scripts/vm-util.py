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

    if args.headless or args.display == "none":
        cmd += ["-display", "none"]
    else:
        cmd += ["-display", f"{args.display},zoom-to-fit=off"]
    if args.serial != "none":
        cmd += ["-serial", args.serial]

    if arch == "x86_64":
        cmd += ["-machine", "q35,smm=off", "-rtc", "base=localtime,clock=host"]
        if not (args.headless or args.display == "none"):
            cmd += ["-device", "virtio-vga"]
    elif arch == "riscv64" or arch == "aarch64":
        machine = "virt,acpi=off" + (",gic-version=3" if arch == "aarch64" else "")
        cmd += [
            "-machine",
            machine,
            "-device",
            "ramfb",
            "-device",
            "virtio-gpu-pci",
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

    if args.iso:
        cmd += ["-cdrom", str(args.iso)]
    if not image.exists() and not args.iso:
        sys.exit(
            f"vm-util: missing disk image {root_relative(image)} "
            f"(build it per the README) or pass --iso"
        )
    if image.exists():
        cmd += [
            "-drive",
            f"format=raw,file={image},if=none,id=disk",
            "-device",
            "nvme,serial=FAKE_SERIAL_ID,drive=disk,bootindex=1",
        ]

    if args.nic != "none":
        cmd += [
            "-netdev",
            "user,id=net0",
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
    run.add_argument("--iso", help="boot from this ISO (added as a CD-ROM)")
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
