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

MINIMAL_PKGS = base-files zinnia zinnia-utils zinnia-devd limine mlibc dinit bash coreutils dhcpcd xbps

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
