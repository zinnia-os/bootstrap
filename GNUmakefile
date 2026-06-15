# ---------------
# Generic targets
# ---------------

ARCH ?= x86_64

.PHONY: all
all: minimal-install image

# Cleans up the entire build directory
.PHONY: clean
clean:
	rm -rf build-$(ARCH)
	rm -rf .jinx-cache
	rm -rf sources
	@echo "Cleaned repository"

# -------------
# Jinx packages
# -------------

build-$(ARCH)/.jinx-parameters:
	@mkdir -p build-$(ARCH)
	@cd build-$(ARCH) && ../jinx/jinx init .. ARCH=$(ARCH)

# Build all packages
.PHONY: full-install
full-install: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx update '*'
	@cd build-$(ARCH) && sudo ../jinx/jinx install sysroot '*'

MINIMAL_PKGS = base-files zinnia zinnia-utils limine mlibc dinit zinnia-devd seatd weston bash coreutils fastfetch

# Build only a minimal selection of packages
.PHONY: minimal-install
minimal-install: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx update $(MINIMAL_PKGS)
	@cd build-$(ARCH) && sudo ../jinx/jinx install sysroot $(MINIMAL_PKGS)

# --------------
# Image creation
# --------------

build-$(ARCH)/zinnia.img:
	@PATH=$$PATH:/usr/sbin:/sbin ./tasks/empty-image.sh $@ 4G 256M

.PHONY: build-$(ARCH)/initramfs.tar
build-$(ARCH)/initramfs.tar:
	./tasks/make-initramfs.sh \
		jinx/jinx \
		build-$(ARCH) \
		$@

# Build a disk image for direct use
.PHONY: image
image: build-$(ARCH)/.jinx-parameters build-$(ARCH)/zinnia.img build-$(ARCH)/initramfs.tar
		@PATH=$$PATH:/usr/sbin:/sbin \
	./tasks/make-image.sh \
		build-$(ARCH)/sysroot \
		build-$(ARCH)/initramfs.tar \
		build-$(ARCH)/zinnia.img \
		$(ARCH)

# Build an ISO image
.PHONY: iso
iso: build-$(ARCH)/.jinx-parameters build-$(ARCH)/initramfs.tar
	./tasks/make-iso.sh \
		build-$(ARCH)/sysroot \
		build-$(ARCH)/initramfs.tar \
		build-$(ARCH)/zinnia.iso \
		$(ARCH)

# -----------
# Development
# -----------

# Shortcut to build and reinstall the kernel
.PHONY: remake-kernel
remake-kernel: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx build zinnia
	@cd build-$(ARCH) && sudo ../jinx/jinx reinstall sysroot zinnia
	@cd build-$(ARCH) && ../jinx/jinx reinstall initramfs zinnia

ovmf/ovmf-code-$(ARCH).fd:
	mkdir -p ovmf
	curl -Lo $@ https://github.com/osdev0/edk2-ovmf-nightly/releases/download/nightly-2025-03-03/ovmf-code-$(ARCH).fd
	case "$(ARCH)" in \
		aarch64) dd if=/dev/zero of=$@ bs=1 count=0 seek=67108864 2>/dev/null;; \
		riscv64) dd if=/dev/zero of=$@ bs=1 count=0 seek=33554432 2>/dev/null;; \
	esac

SMP ?= 4
MEM ?= 2G
KVM ?= 1
QEMUFLAGS ?=

override QEMUFLAGS += \
	-display gtk,zoom-to-fit=off \
	-serial stdio \
	-m $(MEM) \
	-smp $(SMP) \
	-no-reboot \
	-no-shutdown \
	-drive if=pflash,unit=0,format=raw,file=ovmf/ovmf-code-$(ARCH).fd,readonly=on

ifeq ($(KVM), 1)
ifeq ($(shell test -r /dev/kvm && echo $(ARCH)),$(shell uname -m))
override QEMUFLAGS += -cpu host,migratable=off -accel kvm
else
override QEMUFLAGS += -cpu max -accel tcg
endif
else
override QEMUFLAGS += -cpu max -accel tcg
endif

ifeq ($(ARCH),x86_64)
override QEMUFLAGS += \
	-device virtio-vga \
	-rtc base=localtime,clock=host \
	-machine q35,smm=off
endif

ifeq ($(ARCH),riscv64)
override QEMUFLAGS += \
	-device ramfb \
	-device virtio-gpu-pci \
	-machine virt,acpi=off
endif

.PHONY: qemu
qemu: ovmf/ovmf-code-$(ARCH).fd build-$(ARCH)/zinnia.img
	qemu-system-$(ARCH) $(QEMUFLAGS) \
		-drive format=raw,file=build-$(ARCH)/zinnia.img,if=none,id=disk \
		-device nvme,serial=FAKE_SERIAL_ID,drive=disk,bootindex=1

.PHONY: qemu-iso
qemu-iso: ovmf/ovmf-code-$(ARCH).fd build-$(ARCH)/zinnia.iso
	qemu-system-$(ARCH) $(QEMUFLAGS) -cdrom build-$(ARCH)/zinnia.iso \
		-drive format=raw,file=build-$(ARCH)/zinnia.img,if=none,id=disk \
		-device nvme,serial=FAKE_SERIAL_ID,drive=disk,bootindex=1
