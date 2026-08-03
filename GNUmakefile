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
	rm -rf host-sources
	@echo "Cleaned repository"

# -------------
# Jinx packages
# -------------

build-$(ARCH)/.jinx-parameters:
	@mkdir -p build-$(ARCH)
	@cd build-$(ARCH) && ../jinx/jinx init .. ARCH=$(ARCH)

MINIMAL_PKGS = base-system
LIVE_PKGS = zinnia-installer zinnia-live

# Build only a minimal selection of packages
.PHONY: minimal-install
minimal-install: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx update -b $(MINIMAL_PKGS)
	@cd build-$(ARCH) && sudo ../jinx/jinx install sysroot $(MINIMAL_PKGS)

# Build the package selection that goes onto the live installation medium
.PHONY: live-install
live-install: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx update -b $(LIVE_PKGS)
	@cd build-$(ARCH) && sudo ../jinx/jinx install live-sysroot $(LIVE_PKGS)

# Build all packages
.PHONY: full-install
full-install: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx update -b '*'
	@cd build-$(ARCH) && sudo ../jinx/jinx install sysroot '*'

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

# Build a live installation medium
.PHONY: live
live: build-$(ARCH)/.jinx-parameters live-install build-$(ARCH)/initramfs.tar
		@PATH=$$PATH:/usr/sbin:/sbin \
	./tasks/make-live-image.sh \
		build-$(ARCH)/live-sysroot \
		build-$(ARCH)/initramfs.tar \
		build-$(ARCH)/zinnia-live.img \
		$(ARCH)

# -----------
# Development
# -----------

# Shortcut to build and reinstall the kernel
.PHONY: remake-kernel
remake-kernel: build-$(ARCH)/.jinx-parameters
	@cd build-$(ARCH) && ../jinx/jinx build zinnia
	@cd build-$(ARCH) && sudo ../jinx/jinx install -f sysroot zinnia
	@cd build-$(ARCH) && ../jinx/jinx install -f initramfs zinnia
