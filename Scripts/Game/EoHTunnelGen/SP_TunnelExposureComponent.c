//! On every piece of the tunnel test kit (TT_). While the camera is inside one, the camera's exposure is held at one
//! level instead of the game's own: left to itself the game brightens the picture in the dark until anything with a
//! little light on it (the player's own body) glows, and brightens it by a different amount in every corner of the
//! tunnels. In an entrance it comes in by how deep under the ground the camera is. Out in the open again, the game's
//! exposure takes over. Modelled on the EoH tunnel network's EOH_ProcSight hold.
[ComponentEditorProps(category: "EoH/Tunnels", description: "Holds the camera's exposure while it is inside this tunnel piece")]
class SP_TunnelExposureComponentClass : ScriptComponentClass
{
}

class SP_TunnelExposureComponent : ScriptComponent
{
	[Attribute("0", UIWidgets.CheckBox, "An entrance: the picture darkens by how deep under the ground the camera is, not all at once")]
	protected bool m_bEntrance;

	[Attribute("0.005", UIWidgets.EditBox, "How bright the picture is held in the tunnels (the camera's exposure gain), the same by day and by night. Lower is darker; 0.08 was too dark for the unlit kit")]
	protected float m_fTunnelGain;

	[Attribute("0", UIWidgets.CheckBox, "Tells the engine this piece is a dominant object that is not culled the standard way (EntityFlags.FEATURE), to try to stop tunnel pieces vanishing past about 20 m underground. Draws nothing; may cost frame time. Off unless you are testing")]
	protected bool m_bKeepRendered;

	[Attribute("0", UIWidgets.CheckBox, "Take part in the exposure control (held exposure, colour grade, per-soldier probe, flashlight boost). Off: only the no-cull flag, and the engine's own exposure with the piece's probe, as vanilla interiors do")]
	protected bool m_bExposureControl;

	protected static ref array<SP_TunnelExposureComponent> s_aPieces;
	protected vector m_vOrigin;
	protected vector m_vMins;
	protected vector m_vMaxs;
	protected static SP_TunnelExposureComponent s_LastPiece;     // the piece the camera was in last: checked first
	protected static float s_fDark;
	protected static int s_iNextScan;
	protected static bool s_bFeatureOff;
	protected static float s_fDiagGain;          // diag values, read ten times a second (not every frame)
	protected static bool s_bDiagNoGrade;
	protected static bool s_bDiagLog;
	protected static bool s_bDiagHoldOff;
	protected static bool s_bDiagTorchOff;
	protected static float s_fSentGain = -1;

	// A small, completely black probe carried by every soldier underground (EoH's fix for the "blue ghost"): the walls
	// take no sky light by material, characters can't, and whatever reaches them the held exposure would blow up
	protected static const ResourceName MAN_PROBE = "{BB22F0555C450BAA}Prefabs/Tunnels/TT/TT_ManProbe.et";
	protected static ref array<IEntity> s_aProbeMen;
	protected static ref array<IEntity> s_aManProbes;
	protected static ref Resource s_ManProbeRes;
	protected static int s_iNextManTick;

	// The player's flashlight underground: at a dark picture the game's torch alone is too weak, so while it is on a soft
	// spill round the holder and a beam along the view are added (EoH's torch lights, EOH_ProcData.UpdateSpill)
	protected static const float SPILL_LV = 5;
	protected static const float BEAM_LV = 6.5;
	protected static const float BEAM_CONE = 35;
	protected static LightEntity s_Spill;
	protected static LightEntity s_Beam;
	protected static bool s_bTorchOn;
	protected static int s_iNextTorchCheck;
	protected static float s_fGain = 0.005;
	protected static float s_fOutsideGain = 0.02;	// what the game's exposure made of the open air, last seen
	protected static float s_fHeldStops;
	protected static int s_iHeldCamera = -1;
	protected static int s_iLastFrame;
	protected static int s_iOutSince;
	protected static int s_iLastLog;

	//------------------------------------------------------------------------------------------------
	override void OnPostInit(IEntity owner)
	{
		// The cull flag works in the editor view too (the exposure hold below does not)
		if (m_bKeepRendered)
			owner.SetFlags(EntityFlags.FEATURE, false);

		ArmaReforgerScripted game = GetGame();
		if (!game || !game.InPlayMode() || System.IsConsoleApp() || !m_bExposureControl)
			return;

		if (!s_aPieces)
		{
			s_aPieces = {};
			s_iLastFrame = System.GetTickCount();
			game.GetCallqueue().CallLater(Expose, 0, true);
		}

		s_aPieces.Insert(this);
		m_vOrigin = owner.GetOrigin();
		owner.GetBounds(m_vMins, m_vMaxs);
		s_fGain = Math.Clamp(m_fTunnelGain, 0.0005, 2);
		RegisterDiag();
	}

	//------------------------------------------------------------------------------------------------
	// Live tuning in play mode: diag menu (Win+Alt) > Tunnels. The slider starts at the prefab's value; moving it
	// overrides every piece at once, so the right value can be found standing in the cave.
	// ids come from the vanilla diag enum (modded below): free numbers of our own crashed the engine
	protected static const int DIAG_MENU = SCR_DebugMenuID.SP_TUNNELS_MENU;
	protected static const int DIAG_GAIN = SCR_DebugMenuID.SP_TUNNELS_GAIN;
	protected static const int DIAG_NO_GRADE = SCR_DebugMenuID.SP_TUNNELS_NO_GRADE;
	protected static const int DIAG_LOG = SCR_DebugMenuID.SP_TUNNELS_LOG;
	protected static const int DIAG_NO_FEATURE = SCR_DebugMenuID.SP_TUNNELS_NO_FEATURE;
	protected static const int DIAG_HOLD_OFF = SCR_DebugMenuID.SP_TUNNELS_HOLD_OFF;
	protected static const int DIAG_TORCH_OFF = SCR_DebugMenuID.SP_TUNNELS_TORCH_OFF;
	protected static bool s_bDiag;
	protected static float s_fDiagStart;

	protected static void RegisterDiag()
	{
		if (s_bDiag)
			return;

		s_bDiag = true;
		s_fDiagStart = s_fGain;
		DiagMenu.RegisterMenu(DIAG_MENU, "Tunnels", "");
		DiagMenu.RegisterRange(DIAG_GAIN, "", "Exposure gain", "Tunnels", string.Format("0.001, 0.5, %1, 0.001", s_fGain));
		DiagMenu.RegisterBool(DIAG_NO_GRADE, "", "Colour grade off", "Tunnels");
		DiagMenu.RegisterBool(DIAG_LOG, "", "Log exposure", "Tunnels");
		DiagMenu.RegisterBool(DIAG_NO_FEATURE, "", "No-cull flag off (compare FPS)", "Tunnels");
		DiagMenu.RegisterBool(DIAG_HOLD_OFF, "", "Exposure hold off (engine + probes only)", "Tunnels");
		DiagMenu.RegisterBool(DIAG_TORCH_OFF, "", "Flashlight boost off", "Tunnels");
	}

	//! Diag 'No-cull flag off': takes EntityFlags.FEATURE off every piece that had it (and back on), to compare frame rates
	protected static void FeatureSwitch()
	{
		if (!s_bDiag)
			return;

		bool off = DiagMenu.GetBool(DIAG_NO_FEATURE);
		if (off == s_bFeatureOff)
			return;

		s_bFeatureOff = off;
		foreach (SP_TunnelExposureComponent piece : s_aPieces)
		{
			if (!piece || !piece.m_bKeepRendered || !piece.GetOwner())
				continue;

			if (off)
				piece.GetOwner().ClearFlags(EntityFlags.FEATURE, false);
			else
				piece.GetOwner().SetFlags(EntityFlags.FEATURE, false);
		}

		string state = "ON";
		if (off)
			state = "OFF";

		Print(string.Format("SP_TunnelExposure: no-cull flag %1 on %2 pieces", state, s_aPieces.Count()));
	}

	//! The gain in use: the diag slider once it has been moved, else the prefab's
	protected static float Gain()
	{
		if (s_bDiag && s_fDiagGain > 0.001 && Math.AbsFloat(s_fDiagGain - s_fDiagStart) > 0.0001)
			return s_fDiagGain;

		return s_fGain;
	}

	//! Reads the diag menu (called from the 10 Hz scan only)
	protected static void ReadDiag()
	{
		if (!s_bDiag)
			return;

		s_fDiagGain = DiagMenu.GetRangeValue(DIAG_GAIN);
		s_bDiagNoGrade = DiagMenu.GetBool(DIAG_NO_GRADE);
		s_bDiagLog = DiagMenu.GetBool(DIAG_LOG);
		s_bDiagHoldOff = DiagMenu.GetBool(DIAG_HOLD_OFF);
		s_bDiagTorchOff = DiagMenu.GetBool(DIAG_TORCH_OFF);
	}

	//------------------------------------------------------------------------------------------------
	override void OnDelete(IEntity owner)
	{
		if (!s_aPieces)
			return;

		s_aPieces.RemoveItem(this);
		if (s_LastPiece == this)
			s_LastPiece = null;
		if (s_aPieces.IsEmpty())
		{
			s_aPieces = null;
			ArmaReforgerScripted game = GetGame();
			if (game)
			{
				game.GetCallqueue().Remove(Expose);
				Let(game.GetWorld());
				DropManProbes();
				DropTorchLights();
				s_bTorchOn = false;
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Is the player's own flashlight on, while the camera is underground? (checked every 0.3 s)
	protected static void CheckTorch(int now)
	{
		if (now < s_iNextTorchCheck)
			return;

		s_iNextTorchCheck = now + 300;
		s_bTorchOn = false;
		if (s_fDark < 0.3 || s_bDiagTorchOff)
			return;

		IEntity me = SCR_PlayerController.GetLocalControlledEntity();
		if (!me)
			return;

		SCR_GadgetManagerComponent gadgets = SCR_GadgetManagerComponent.GetGadgetManager(me);
		if (!gadgets)
			return;

		array<SCR_GadgetComponent> torches = gadgets.GetGadgetsByType(EGadgetType.FLASHLIGHT);
		foreach (SCR_GadgetComponent torch : torches)
		{
			if (torch && torch.IsToggledOn())
				s_bTorchOn = true;
		}
	}

	//------------------------------------------------------------------------------------------------
	//! The spill and the beam follow the view every frame (only while the torch is on)
	protected static void UpdateTorch(vector camera[4])
	{
		vector spillAt = camera[3] + camera[2] * 0.6 + "0 0.2 0";
		vector beamAt = camera[3] + camera[2] * 0.3 - "0 0.15 0";
		if (s_bTorchOn && !s_Spill)
		{
			s_Spill = LightEntity.CreateLight(LightType.POINT, 0, 5, Color.FromRGBA(255, 235, 200, 255), SPILL_LV, spillAt);
			s_Beam = LightEntity.CreateLight(LightType.SPOT, 0, 25, Color.FromRGBA(255, 240, 215, 255), BEAM_LV, beamAt, camera[2]);
			if (s_Spill)
				s_Spill.SetLensFlareType(LightLensFlareType.Disabled);

			if (s_Beam)
			{
				s_Beam.SetLensFlareType(LightLensFlareType.Disabled);
				s_Beam.SetConeAngle(BEAM_CONE);
				s_Beam.SetConeAngleAttenuation(0.4);
			}
		}
		else if (!s_bTorchOn && s_Spill)
		{
			DropTorchLights();
		}

		if (s_Spill)
		{
			s_Spill.SetOrigin(spillAt);
			s_Spill.Update();
		}

		if (s_Beam)
		{
			s_Beam.SetOrigin(beamAt);
			s_Beam.SetLightDirection(camera[2]);
			s_Beam.Update();
		}
	}

	//------------------------------------------------------------------------------------------------
	protected static void DropTorchLights()
	{
		if (s_Spill)
			delete s_Spill;

		s_Spill = null;
		if (s_Beam)
			delete s_Beam;

		s_Beam = null;
	}

	//------------------------------------------------------------------------------------------------
	//! How dark it is at this spot: inside any piece (an entrance by depth), else 0
	protected static float DarkAt(vector pos, BaseWorld world)
	{
		foreach (SP_TunnelExposureComponent piece : s_aPieces)
		{
			if (!piece)
				continue;

			float d = piece.DarknessAt(pos, world);
			if (d > 0)
				return d;
		}

		return 0;
	}

	//------------------------------------------------------------------------------------------------
	//! Twice a second: soldiers within 40 m of the camera who are underground get a black probe, the others give theirs
	//! back. Local only (each machine for its own picture), nothing is sent.
	protected static void ManProbeTick(BaseWorld world, vector eye)
	{
		if (!s_aProbeMen)
		{
			s_aProbeMen = {};
			s_aManProbes = {};
		}

		for (int i = s_aProbeMen.Count() - 1; i >= 0; i--)
		{
			IEntity carrier = s_aProbeMen[i];
			IEntity carried = s_aManProbes[i];
			if (carrier && carried && DarkAt(carrier.GetOrigin() + "0 0.9 0", world) > 0)
				continue;

			if (carried)
				SCR_EntityHelper.DeleteEntityAndChildren(carried);

			s_aProbeMen.Remove(i);
			s_aManProbes.Remove(i);
		}

		SP_TunnelExposureComponent any = s_LastPiece;
		if (!any)
		{
			foreach (SP_TunnelExposureComponent piece : s_aPieces)
			{
				if (piece)
				{
					any = piece;
					break;
				}
			}
		}

		if (any)
			world.QueryEntitiesBySphere(eye, 40, any.OnManQuery, null, EQueryEntitiesFlags.DYNAMIC);
	}

	//------------------------------------------------------------------------------------------------
	protected bool OnManQuery(IEntity entity)
	{
		ChimeraCharacter man = ChimeraCharacter.Cast(entity);
		if (!man || s_aProbeMen.Contains(man))
			return true;

		BaseWorld world = man.GetWorld();
		if (!world || DarkAt(man.GetOrigin() + "0 0.9 0", world) <= 0)
			return true;

		if (!s_ManProbeRes)
			s_ManProbeRes = Resource.Load(MAN_PROBE);

		if (!s_ManProbeRes || !s_ManProbeRes.IsValid())
			return false;

		EntitySpawnParams params = new EntitySpawnParams();
		params.TransformMode = ETransformMode.WORLD;
		params.Transform[3] = man.GetOrigin() + "0 1 0";
		IEntity probe = GetGame().SpawnEntityPrefabLocal(s_ManProbeRes, world, params);
		if (!probe)
			return true;

		man.AddChild(probe, -1);
		vector offset[4];
		Math3D.MatrixIdentity4(offset);
		offset[3] = Vector(0, 1, 0);
		probe.SetLocalTransform(offset);
		probe.Update();
		s_aProbeMen.Insert(man);
		s_aManProbes.Insert(probe);
		return true;
	}

	//------------------------------------------------------------------------------------------------
	protected static void DropManProbes()
	{
		if (!s_aManProbes)
			return;

		foreach (IEntity carried : s_aManProbes)
		{
			if (carried)
				SCR_EntityHelper.DeleteEntityAndChildren(carried);
		}

		s_aManProbes.Clear();
		s_aProbeMen.Clear();
	}

	//------------------------------------------------------------------------------------------------
	//! 1 inside this piece, 0 outside it; in an entrance, by how deep under the ground
	protected float DarknessAt(vector pos, BaseWorld world)
	{
		if (vector.DistanceSq(m_vOrigin, pos) > 400)
			return 0;

		IEntity owner = GetOwner();
		if (!owner)
			return 0;

		vector local = owner.CoordToLocal(pos);
		for (int i = 0; i < 3; i++)
		{
			if (local[i] < m_vMins[i] || local[i] > m_vMaxs[i])
				return 0;
		}

		if (!m_bEntrance)
			return 1;

		float depth = world.GetSurfaceY(pos[0], pos[2]) - pos[1];
		return Math.Clamp((depth - 0.5) / 2.5, 0, 1);
	}

	//------------------------------------------------------------------------------------------------
	//! Every frame
	protected static void Expose()
	{
		ArmaReforgerScripted game = GetGame();
		if (!game || !s_aPieces)
			return;

		BaseWorld world = game.GetWorld();
		if (!world)
			return;

		int now = System.GetTickCount();
		float frame = Math.Clamp((now - s_iLastFrame) * 0.001, 0, 0.1);
		s_iLastFrame = now;

		vector view[4];
		world.GetCurrentCamera(view);
		int camera = world.GetCurrentCameraId();
		if (s_iHeldCamera >= 0 && s_iHeldCamera != camera)
			Let(world);

		if (now >= s_iNextScan)
		{
			s_iNextScan = now + 100;
			float found;
			SP_TunnelExposureComponent best;
			if (s_LastPiece)
			{
				found = s_LastPiece.DarknessAt(view[3], world);
				if (found > 0)
					best = s_LastPiece;
			}

			if (found < 1)
			{
				foreach (SP_TunnelExposureComponent piece : s_aPieces)
				{
					if (!piece || piece == s_LastPiece)
						continue;

					float d = piece.DarknessAt(view[3], world);
					if (d > found)
					{
						found = d;
						best = piece;
						if (found >= 1)
							break;
					}
				}
			}

			s_fDark = found;
			s_LastPiece = best;
			ReadDiag();
			FeatureSwitch();
			if (now >= s_iNextManTick)
			{
				s_iNextManTick = now + 500;
				ManProbeTick(world, view[3]);
			}
		}

		float dark = s_fDark;
		CheckTorch(now);
		UpdateTorch(view);
		if (s_bDiagHoldOff)
		{
			// comparison: the engine's own exposure with the dark probes' HDR settings, no hold, no grade
			if (s_iHeldCamera >= 0)
				Let(world);

			return;
		}

		float outside = Math.Log2(s_fOutsideGain);
		float gain = Gain();
		float target = outside + (Math.Log2(gain) - outside) * dark;
		if (s_iHeldCamera < 0)
		{
			float seen = world.GetCameraHDRBrightness(camera);
			if (dark < 0.02)
			{
				// Out in the open: remember what the game's exposure makes of it, to hand back to on the way out
				if (seen > 0.001 && seen < 4)
					s_fOutsideGain = seen;

				return;
			}

			// Walking in: held from where the game's exposure is, so nothing jumps; arriving deep in: straight there
			if (dark > 0.5 || seen < 0.001 || seen > 4)
				s_fHeldStops = target;
			else
				s_fHeldStops = Math.Log2(seen);

			s_iHeldCamera = camera;
			s_iOutSince = 0;
		}

		s_fHeldStops = s_fHeldStops + (target - s_fHeldStops) * Math.Min(1, frame * 5);

		// Back out in the open and level with it: the game's own exposure again
		if (dark <= 0)
		{
			if (s_iOutSince == 0)
				s_iOutSince = now;

			if (now - s_iOutSince > 400 && Math.AbsFloat(s_fHeldStops - outside) < 0.05)
			{
				Let(world);
				return;
			}
		}
		else
		{
			s_iOutSince = 0;
		}

		float send = Math.Pow(2, s_fHeldStops);
		if (s_fSentGain < 0 || Math.AbsFloat(send - s_fSentGain) > s_fSentGain * 0.003)
		{
			world.SetCameraHDRBrightness(camera, send);
			s_fSentGain = send;
		}

		// The sky's haze lies over everything that takes fog, soldiers included (their materials can't switch it off):
		// a gentle grade pulls the darkest tones back to black, in four steps by how far in the camera is
		int step = Math.Round(Math.Clamp(dark, 0, 1) * GRADE_STEPS.Count());
		if (s_bDiagNoGrade)
			step = 0;

		Grade(world, camera, step);
		if (s_bDiagLog && now - s_iLastLog > 1000)
		{
			s_iLastLog = now;
			Print(string.Format("SP_TunnelExposure: gain %1 (prefab %2), held %3, dark %4, grade step %5", gain, s_fGain, Math.Pow(2, s_fHeldStops), dark, step));
		}
	}

	protected static const int GRADE_SLOT = 15;
	protected static const ref array<string> GRADE_STEPS = {"{6E34723529370D85}Assets/Tunnels/TT/Data/TT_Grade_1.emat", "{7812EF9B6FD22828}Assets/Tunnels/TT/Data/TT_Grade_2.emat", "{5C24ECF24988D099}Assets/Tunnels/TT/Data/TT_Grade_3.emat", "{CEEA07629923CFB2}Assets/Tunnels/TT/Data/TT_Grade_4.emat"};
	protected static int s_iGradeStep;
	protected static int s_iGradeCamera = -1;

	//------------------------------------------------------------------------------------------------
	//! The underground grade on this camera at this step (0 off), taken off whichever camera had it before
	protected static void Grade(BaseWorld world, int camera, int step)
	{
		if (!world)
			return;

		if (step == s_iGradeStep && (step == 0 || camera == s_iGradeCamera))
			return;

		if (s_iGradeStep > 0 && s_iGradeCamera >= 0)
			world.SetCameraPostProcessEffect(s_iGradeCamera, GRADE_SLOT, PostProcessEffectType.None, string.Empty);

		s_iGradeStep = 0;
		s_iGradeCamera = -1;
		if (step <= 0 || camera < 0)
			return;

		world.SetCameraPostProcessEffect(camera, GRADE_SLOT, PostProcessEffectType.Colors, GRADE_STEPS[step - 1]);
		s_iGradeStep = step;
		s_iGradeCamera = camera;
	}

	//------------------------------------------------------------------------------------------------
	//! The camera goes back to the game's own exposure, without the grade
	protected static void Let(BaseWorld world)
	{
		if (s_iHeldCamera >= 0 && world)
			world.SetCameraHDRBrightness(s_iHeldCamera, -1);

		Grade(world, -1, 0);
		s_fSentGain = -1;
		s_iHeldCamera = -1;
		s_iOutSince = 0;
	}
}

//! The tunnels' entries in the diag menu (Win+Alt > Tunnels)
modded enum SCR_DebugMenuID
{
	SP_TUNNELS_MENU,
	SP_TUNNELS_GAIN,
	SP_TUNNELS_NO_GRADE,
	SP_TUNNELS_LOG,
	SP_TUNNELS_NO_FEATURE,
	SP_TUNNELS_HOLD_OFF,
	SP_TUNNELS_TORCH_OFF
}
