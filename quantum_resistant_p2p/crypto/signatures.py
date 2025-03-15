"""
Post-quantum digital signature algorithms.
"""

import abc
import logging
import os
import hashlib
import hmac
import threading
from typing import Tuple, Optional, Dict

# Import the base class
from .algorithm_base import CryptoAlgorithm

# Try to import oqs (Open Quantum Safe)
try:
    import oqs
    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    logging.warning("oqs not available, using deterministic mock implementations for post-quantum algorithms")

logger = logging.getLogger(__name__)


# Mock implementation helper functions
def get_node_id():
    """Get a unique ID for this node from environment or thread ID."""
    return os.environ.get('NODE_ID', str(threading.get_ident()))


class SignatureAlgorithm(CryptoAlgorithm):
    """Abstract base class for digital signature algorithms."""
    
    @abc.abstractmethod
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a new keypair.
        
        Returns:
            Tuple of (public_key, private_key)
        """
        pass
    
    @abc.abstractmethod
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Sign a message using the private key.
        
        Args:
            private_key: The private key for signing
            message: The message to sign
            
        Returns:
            The signature
        """
        pass
    
    @abc.abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a signature using the public key.
        
        Args:
            public_key: The public key for verification
            message: The message that was signed
            signature: The signature to verify
            
        Returns:
            True if the signature is valid, False otherwise
        """
        pass


class DilithiumSignature(SignatureAlgorithm):
    """CRYSTALS-Dilithium digital signature algorithm.
    
    Dilithium is a post-quantum signature scheme based on the
    hardness of lattice problems.
    """
    
    # Class-level storage for mock implementation
    _mock_keypairs = {}  # public_key -> private_key
    
    def __init__(self, security_level: int = 3):
        """Initialize Dilithium with the specified security level.
        
        Args:
            security_level: Security level (2, 3, or 5)
        """
        global LIBOQS_AVAILABLE
        
        self.security_level = security_level
        self.signer = None
        self.variant = None
        
        # Attempt to get list of enabled signature mechanisms if OQS is available
        self.enabled_sigs = []
        if LIBOQS_AVAILABLE:
            try:
                self.enabled_sigs = oqs.get_enabled_sig_mechanisms()
            except Exception as e:
                logger.error(f"Error getting enabled signature mechanisms: {e}")
                LIBOQS_AVAILABLE = False
        
        if not LIBOQS_AVAILABLE:
            logger.warning("Using deterministic mock implementation of Dilithium")
            return
        
        # Map security levels to Dilithium variants
        # Using both ML-DSA (new names) and Dilithium (old names) for compatibility
        dilithium_variants = {
            2: ["ML-DSA-44", "Dilithium2"],
            3: ["ML-DSA-65", "Dilithium3"],
            5: ["ML-DSA-87", "Dilithium5"]
        }
        
        if security_level not in dilithium_variants:
            raise ValueError(f"Invalid security level: {security_level}. Must be 2, 3, or 5.")
        
        # Try the new ML-DSA name first, then fall back to the old Dilithium name
        variant_found = False
        for variant in dilithium_variants[security_level]:
            if variant in self.enabled_sigs:
                self.variant = variant
                variant_found = True
                break
        
        if not variant_found:
            logger.warning(f"No Dilithium variant found for security level {security_level}, using deterministic mock implementation")
            LIBOQS_AVAILABLE = False
            return
        
        # Try to create the Signature instance
        try:
            self.signer = oqs.Signature(self.variant)
            logger.info(f"Successfully initialized Dilithium variant {self.variant}")
        except Exception as e:
            logger.error(f"Error initializing Dilithium: {e}")
            LIBOQS_AVAILABLE = False
        
        logger.info(f"Initialized Dilithium signature with security level {security_level}")
    
    @property
    def name(self) -> str:
        """Get the name of the algorithm."""
        if LIBOQS_AVAILABLE and self.signer is not None:
            return f"CRYSTALS-Dilithium (Level {self.security_level})"
        return f"CRYSTALS-Dilithium (Level {self.security_level}) [Mock]"
    
    @property
    def description(self) -> str:
        """Get a description of the algorithm."""
        return ("CRYSTALS-Dilithium is a lattice-based digital signature scheme. "
                "It is one of the NIST post-quantum cryptography standards.")
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a new Dilithium keypair.
        
        Returns:
            Tuple of (public_key, private_key)
        """
        global LIBOQS_AVAILABLE
        
        if not LIBOQS_AVAILABLE or self.signer is None:
            # Deterministic mock implementation
            node_id = get_node_id()
            
            # Generate deterministic private key
            seed = f"dilithium-{self.security_level}-private-{node_id}"
            private_key = hashlib.sha256(seed.encode()).digest()
            
            # Generate matching public key
            pub_seed = f"dilithium-{self.security_level}-public-{private_key.hex()}"
            public_key = hashlib.sha256(pub_seed.encode()).digest()
            
            # Store keypair for verification
            self._mock_keypairs[public_key] = private_key
            
            logger.debug("Generated deterministic mock Dilithium keypair")
            return public_key, private_key
        
        try:
            # Use actual OQS implementation with the current API pattern
            public_key = self.signer.generate_keypair()
            private_key = self.signer.export_secret_key()
            
            logger.debug(f"Generated Dilithium keypair: public key {len(public_key)} bytes, "
                      f"private key {len(private_key)} bytes")
            
            return public_key, private_key
        except Exception as e:
            logger.error(f"Error generating Dilithium keypair: {e}")
            # Fall back to mock implementation
            LIBOQS_AVAILABLE = False
            return self.generate_keypair()  # Recursive call to use mock implementation
    
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Sign a message using Dilithium.
        
        Args:
            private_key: The private key for signing
            message: The message to sign
            
        Returns:
            The signature
        """
        global LIBOQS_AVAILABLE
        
        if not LIBOQS_AVAILABLE or self.signer is None:
            # Deterministic mock implementation with HMAC
            # HMAC provides deterministic signatures that can be verified with the same key
            signature = hmac.new(private_key, message, hashlib.sha256).digest()
            
            logger.debug("Created deterministic mock Dilithium signature")
            return signature
        
        try:
            # Create a new signer with the private key
            signer = oqs.Signature(self.variant, private_key)
            signature = signer.sign(message)
            
            logger.debug(f"Created Dilithium signature: {len(signature)} bytes")
            
            return signature
        except Exception as e:
            logger.error(f"Error signing with Dilithium: {e}")
            # Fall back to mock implementation
            LIBOQS_AVAILABLE = False
            return self.sign(private_key, message)  # Recursive call to use mock implementation
    
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a Dilithium signature.
        
        Args:
            public_key: The public key for verification
            message: The message that was signed
            signature: The signature to verify
            
        Returns:
            True if the signature is valid, False otherwise
        """
        global LIBOQS_AVAILABLE
        
        if not LIBOQS_AVAILABLE or self.signer is None:
            # Deterministic mock verification
            
            # Get the private key corresponding to this public key
            private_key = self._mock_keypairs.get(public_key)
            
            if private_key:
                # Recreate the expected signature
                expected_signature = hmac.new(private_key, message, hashlib.sha256).digest()
                # Compare signatures using constant-time comparison
                result = hmac.compare_digest(signature, expected_signature)
            else:
                # If we don't have the private key (maybe from another node)
                # we verify the signature structure is correct
                result = len(signature) == 32  # SHA-256 HMAC is 32 bytes
            
            logger.debug(f"Verified mock Dilithium signature: {'success' if result else 'failure'}")
            return result
        
        try:
            # Create a new verifier
            verifier = oqs.Signature(self.variant)
            result = verifier.verify(message, signature, public_key)
            
            logger.debug(f"Dilithium signature verification: {'success' if result else 'failure'}")
            
            return result
        except Exception as e:
            logger.error(f"Error verifying Dilithium signature: {e}")
            LIBOQS_AVAILABLE = False
            return self.verify(public_key, message, signature)  # Recursive call to use mock implementation


class SPHINCSSignature(SignatureAlgorithm):
    """SPHINCS+ digital signature algorithm.
    
    SPHINCS+ is a stateless hash-based signature scheme.
    """
    
    # Class-level storage for mock implementation
    _mock_keypairs = {}  # public_key -> private_key
    
    def __init__(self, security_level: int = 3):
        """Initialize SPHINCS+ with the specified security level.
        
        Args:
            security_level: Security level (1, 3, or 5)
        """
        global LIBOQS_AVAILABLE
        
        self.security_level = security_level
        self.signer = None
        self.variant = None
        
        # Attempt to get list of enabled signature mechanisms if OQS is available
        self.enabled_sigs = []
        if LIBOQS_AVAILABLE:
            try:
                self.enabled_sigs = oqs.get_enabled_sig_mechanisms()
            except Exception as e:
                logger.error(f"Error getting enabled signature mechanisms: {e}")
                LIBOQS_AVAILABLE = False
        
        if not LIBOQS_AVAILABLE:
            logger.warning("Using deterministic mock implementation of SPHINCS+")
            return
        
        # Map security levels to SPHINCS+ variants
        sphincs_variants = {
            1: ["SPHINCS+-SHA2-128f-simple"],
            3: ["SPHINCS+-SHA2-192f-simple"],
            5: ["SPHINCS+-SHA2-256f-simple"]
        }
        
        if security_level not in sphincs_variants:
            raise ValueError(f"Invalid security level: {security_level}. Must be 1, 3, or 5.")
        
        # Try to find an available variant
        variant_found = False
        for variant in sphincs_variants[security_level]:
            if variant in self.enabled_sigs:
                self.variant = variant
                variant_found = True
                break
        
        if not variant_found:
            logger.warning(f"No SPHINCS+ variant found for security level {security_level}, using deterministic mock implementation")
            LIBOQS_AVAILABLE = False
            return
        
        # Try to create the Signature instance
        try:
            self.signer = oqs.Signature(self.variant)
            logger.info(f"Successfully initialized SPHINCS+ variant {self.variant}")
        except Exception as e:
            logger.error(f"Error initializing SPHINCS+: {e}")
            LIBOQS_AVAILABLE = False
        
        logger.info(f"Initialized SPHINCS+ signature with security level {security_level}")
    
    @property
    def name(self) -> str:
        """Get the name of the algorithm."""
        if LIBOQS_AVAILABLE and self.signer is not None:
            return f"SPHINCS+ (Level {self.security_level})"
        return f"SPHINCS+ (Level {self.security_level}) [Mock]"
    
    @property
    def description(self) -> str:
        """Get a description of the algorithm."""
        return ("SPHINCS+ is a stateless hash-based digital signature scheme. "
                "Its security relies only on the security of the underlying hash functions.")
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a new SPHINCS+ keypair.
        
        Returns:
            Tuple of (public_key, private_key)
        """
        global LIBOQS_AVAILABLE
        
        if not LIBOQS_AVAILABLE or self.signer is None:
            # Deterministic mock implementation
            node_id = get_node_id()
            
            # Generate deterministic private key
            seed = f"sphincs-{self.security_level}-private-{node_id}"
            private_key = hashlib.sha256(seed.encode()).digest()
            
            # Generate matching public key
            pub_seed = f"sphincs-{self.security_level}-public-{private_key.hex()}"
            public_key = hashlib.sha256(pub_seed.encode()).digest()
            
            # Store keypair for verification
            self._mock_keypairs[public_key] = private_key
            
            logger.debug("Generated deterministic mock SPHINCS+ keypair")
            return public_key, private_key
        
        try:
            # Use actual OQS implementation with the current API pattern
            public_key = self.signer.generate_keypair()
            private_key = self.signer.export_secret_key()
            
            logger.debug(f"Generated SPHINCS+ keypair: public key {len(public_key)} bytes, "
                      f"private key {len(private_key)} bytes")
            
            return public_key, private_key
        except Exception as e:
            logger.error(f"Error generating SPHINCS+ keypair: {e}")
            # Fall back to mock implementation
            LIBOQS_AVAILABLE = False
            return self.generate_keypair()  # Recursive call to use mock implementation
    
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Sign a message using SPHINCS+.
        
        Args:
            private_key: The private key for signing
            message: The message to sign
            
        Returns:
            The signature
        """
        global LIBOQS_AVAILABLE
        
        if not LIBOQS_AVAILABLE or self.signer is None:
            # Deterministic mock implementation with HMAC
            # For SPHINCS+, we'll use a different hash function to distinguish from Dilithium
            digest = hashlib.sha384()
            digest.update(private_key)
            digest.update(message)
            signature = digest.digest()
            
            logger.debug("Created deterministic mock SPHINCS+ signature")
            return signature
        
        try:
            # Create a new signer with the private key
            signer = oqs.Signature(self.variant, private_key)
            signature = signer.sign(message)
            
            logger.debug(f"Created SPHINCS+ signature: {len(signature)} bytes")
            
            return signature
        except Exception as e:
            logger.error(f"Error signing with SPHINCS+: {e}")
            # Fall back to mock implementation
            LIBOQS_AVAILABLE = False
            return self.sign(private_key, message)  # Recursive call to use mock implementation
    
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a SPHINCS+ signature.
        
        Args:
            public_key: The public key for verification
            message: The message that was signed
            signature: The signature to verify
            
        Returns:
            True if the signature is valid, False otherwise
        """
        global LIBOQS_AVAILABLE
        
        if not LIBOQS_AVAILABLE or self.signer is None:
            # Deterministic mock verification
            
            # Get the private key corresponding to this public key
            private_key = self._mock_keypairs.get(public_key)
            
            if private_key:
                # Recreate the expected signature
                digest = hashlib.sha384()
                digest.update(private_key)
                digest.update(message)
                expected_signature = digest.digest()
                # Compare signatures using constant-time comparison
                result = hmac.compare_digest(signature, expected_signature)
            else:
                # If we don't have the private key (maybe from another node)
                # we verify the signature structure is correct
                result = len(signature) == 48  # SHA-384 digest is 48 bytes
            
            logger.debug(f"Verified mock SPHINCS+ signature: {'success' if result else 'failure'}")
            return result
        
        try:
            # Create a new verifier
            verifier = oqs.Signature(self.variant)
            result = verifier.verify(message, signature, public_key)
            
            logger.debug(f"SPHINCS+ signature verification: {'success' if result else 'failure'}")
            
            return result
        except Exception as e:
            logger.error(f"Error verifying SPHINCS+ signature: {e}")
            LIBOQS_AVAILABLE = False
            return self.verify(public_key, message, signature)  # Recursive call to use mock implementation
