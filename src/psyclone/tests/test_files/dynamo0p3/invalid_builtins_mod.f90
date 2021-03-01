! -----------------------------------------------------------------------------
! BSD 3-Clause License
!
! Copyright (c) 2017-2021, Science and Technology Facilities Council
! All rights reserved.
!
! Redistribution and use in source and binary forms, with or without
! modification, are permitted provided that the following conditions are met:
!
! * Redistributions of source code must retain the above copyright notice, this
!   list of conditions and the following disclaimer.
!
! * Redistributions in binary form must reproduce the above copyright notice,
!   this list of conditions and the following disclaimer in the documentation
!   and/or other materials provided with the distribution.
!
! * Neither the name of the copyright holder nor the names of its
!   contributors may be used to endorse or promote products derived from
!   this software without specific prior written permission.
!
! THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
! "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
! LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
! FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
! COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
! INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
! BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
! LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
! CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
! LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
! ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
! POSSIBILITY OF SUCH DAMAGE.
! -----------------------------------------------------------------------------
! Authors R. W. Ford and A. R. Porter, STFC Daresbury Lab
! Modified I. Kavcic, Met Office

!> @brief Broken meta-data for the LFRic built-in operations.
!> @details This meta-data is purely to provide PSyclone with a
!> specification of each operation.
!!         This specification is used for correctness checking as well as
!!         to enable optimisations of invokes containing calls to
!!         built-in operations.
!!         The actual implementation of these built-ins is
!!         generated by PSyclone (hence the empty ..._code routines in
!!         this file).
module dynamo0p3_builtins_mod

  !> An invalid built-in that writes to more than one field
  type, public, extends(kernel_type) :: aX_plus_Y
     private
     type(arg_type) :: meta_args(4) = (/                              &
          arg_type(GH_FIELD,  GH_REAL, GH_WRITE, ANY_SPACE_1),        &
          arg_type(GH_SCALAR, GH_REAL, GH_READ              ),        &
          arg_type(GH_FIELD,  GH_REAL, GH_READ,  ANY_SPACE_1),        &
          arg_type(GH_FIELD,  GH_REAL, GH_WRITE, ANY_SPACE_1)         &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: aX_plus_Y_code
  end type aX_plus_Y

  !> An invalid built-in that updates two arguments where one is a scalar
  !! reduction (gh_sum) and the other is a field with gh_readwrite access
  type, public, extends(kernel_type) :: inc_aX_plus_Y
     private
     type(arg_type) :: meta_args(3) = (/                              &
          arg_type(GH_SCALAR, GH_REAL, GH_SUM                   ),    &
          arg_type(GH_FIELD,  GH_REAL, GH_READWRITE, ANY_SPACE_1),    &
          arg_type(GH_FIELD,  GH_REAL, GH_READ,      ANY_SPACE_1)     &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: inc_aX_plus_Y_code
  end type inc_aX_plus_Y

  !> An invalid built-in that doesn't write to any argument
  type, public, extends(kernel_type) :: aX_plus_bY
     private
     type(arg_type) :: meta_args(5) = (/                              &
          arg_type(GH_FIELD,  GH_REAL, GH_READ, ANY_SPACE_1),         &
          arg_type(GH_SCALAR, GH_REAL, GH_READ             ),         &
          arg_type(GH_FIELD,  GH_REAL, GH_READ, ANY_SPACE_1),         &
          arg_type(GH_SCALAR, GH_REAL, GH_READ             ),         &
          arg_type(GH_FIELD,  GH_REAL, GH_READ, ANY_SPACE_1)          &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: aX_plus_bY_code
  end type aX_plus_bY

  !> An invalid built-in that writes to two field arguments
  !! but with different access types - one is gh_write, one is gh_readwrite.
  type, public, extends(kernel_type) :: inc_aX_plus_bY
     private
     type(arg_type) :: meta_args(4) = (/                              &
          arg_type(GH_SCALAR, GH_REAL, GH_READ                  ),    &
          arg_type(GH_FIELD,  GH_REAL, GH_READWRITE, ANY_SPACE_1),    &
          arg_type(GH_SCALAR, GH_REAL, GH_READ                  ),    &
          arg_type(GH_FIELD,  GH_REAL, GH_WRITE,     ANY_SPACE_1)     &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: inc_aX_plus_bY_code
  end type inc_aX_plus_bY

  !> An invalid built-in that has no field arguments
  type, public, extends(kernel_type) :: setval_X
     private
     type(arg_type) :: meta_args(2) = (/                              &
          arg_type(GH_SCALAR, GH_REAL, GH_SUM),                       &
          arg_type(GH_SCALAR, GH_REAL, GH_READ)                       &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: setval_X_code
  end type setval_X

  !> Invalid built-in that claims to take an operator as an argument
  type, public, extends(kernel_type) :: a_times_X
     private
     type(arg_type) :: meta_args(3) = (/                                      &
          arg_type(GH_FIELD,    GH_REAL, GH_WRITE, ANY_SPACE_1             ), &
          arg_type(GH_SCALAR,   GH_REAL, GH_READ                           ), &
          arg_type(GH_OPERATOR, GH_REAL, GH_READ,  ANY_SPACE_1, ANY_SPACE_1)  &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: a_times_X_code
  end type a_times_X

  !> Invalid built-in that has arguments on different spaces
  type, public, extends(kernel_type) :: inc_X_divideby_Y
     private
     type(arg_type) :: meta_args(2) = (/                              &
          arg_type(GH_FIELD, GH_REAL, GH_READWRITE, ANY_SPACE_1),     &
          arg_type(GH_FIELD, GH_REAL, GH_READ,      ANY_SPACE_2)      &
          /)
     integer :: operates_on = DOF
   contains
     procedure, nopass :: inc_X_divideby_Y_code
  end type inc_X_divideby_Y

  ! TODO in #1107: Add a check that mixing will only be allowed for the
  ! built-ins that convert 'real'- to 'integer'-valued fields and vice-versa.

contains

  subroutine aX_plus_Y_code()
  end subroutine aX_plus_Y_code

  subroutine inc_aX_plus_Y_code()
  end subroutine inc_aX_plus_Y_code

  subroutine aX_plus_bY_code()
  end subroutine aX_plus_bY_code

  subroutine inc_aX_plus_bY_code()
  end subroutine inc_aX_plus_bY_code

  subroutine setval_X_code()
  end subroutine setval_X_code

  subroutine a_times_X_code()
  end subroutine a_times_X_code

  subroutine inc_X_divideby_Y_code()
  end subroutine inc_X_divideby_Y_code

end module dynamo0p3_builtins_mod
